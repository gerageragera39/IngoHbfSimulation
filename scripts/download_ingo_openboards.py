#!/usr/bin/env python3
"""Download DB OpenBoards data for a complete Ingolstadt Hbf calendar day.
Python 3.10+; on Windows install tzdata. No third-party HTTP library needed.
API docs: https://developer-docs.deutschebahn.com/doku/apis/Open-API-Baustein-OpenBoards-14071662
"""
from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import json
import os
import re
import sys
import time
import math
from email.utils import parsedate_to_datetime
from collections import Counter, defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

BASE = 'https://apis.deutschebahn.com/db-api-marketplace/apis/open-boards/v1'
EVA = '8000183'
LIMIT = 50
MIN_REQUEST_INTERVAL = 0.2  # conservative per-process spacing; below 10 requests/second
UTC = timezone.utc


def dump(path, obj):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def write_csv(path, rows, fields):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def dt(value):
    if not value:
        return None
    t = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if t.tzinfo is None:
        raise ValueError('API returned timestamp without timezone: ' + value)
    return t.astimezone(UTC)


def iso(t):
    return t.isoformat() if t else ''


def text(v):
    return '' if v is None else str(v)


def target(category, line):
    """Keep every RE, RB and ICE; retain unnumbered regional trains for review."""
    c = re.sub(r'\s+', '', category.upper())
    l = re.sub(r'\s+', '', line.upper())
    if c == 'ICE':
        return 'ICE'
    m = re.fullmatch(r'(RE|RB)([0-9]+[A-Z]?)?', c)
    if not m:
        return ''
    prefix, number = m.groups()
    if number:
        return prefix + number
    if re.fullmatch(prefix + r'[0-9]+[A-Z]?', l):
        return l
    if re.fullmatch(r'[0-9]+[A-Z]?', l):
        return prefix + l
    # Do not silently drop regional services when their line ID is absent.
    return prefix


def platform(v):
    # Preserve the source name separately; never infer a numeric track from a suffix.
    v = text(v).strip()
    m = re.fullmatch(r'(?:Gleis\s*)?(\d+)', v, re.I)
    return int(m.group(1)) if m else None


class NoRedirect(HTTPRedirectHandler):
    """Never send DB credentials to a redirect target or issue an unpaced request."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# One sequential request per call, no automatic HTTP redirects.
_HTTP = build_opener(NoRedirect())


def urlopen(req, timeout):
    return _HTTP.open(req, timeout=timeout)


class RequestPacer:
    def __init__(self, pause):
        self.interval = max(MIN_REQUEST_INTERVAL, pause)
        self.last = None
        self.recent = deque()
        self.attempts = 0
        self.max_in_one_second = 0

    def before_request(self):
        if self.last is not None:
            while True:
                remaining = self.last + self.interval - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(remaining)
        now = time.monotonic()
        self.last = now
        self.attempts += 1
        while self.recent and now - self.recent[0] >= 1.0:
            self.recent.popleft()
        self.recent.append(now)
        self.max_in_one_second = max(self.max_in_one_second, len(self.recent))

    def stats(self):
        return {'minimum_request_spacing_seconds': self.interval,
                'http_attempts': self.attempts,
                'max_attempts_in_rolling_one_second': self.max_in_one_second,
                'subscription_limit_per_second': 10,
                'scope': 'this process only; includes retries; cached reads excluded'}


def retry_seconds(value, attempt):
    fallback = 2 ** (attempt + 1)
    if not value:
        return fallback
    try:
        delay = float(value)
        if math.isfinite(delay):
            return max(fallback, delay)
    except ValueError:
        pass
    try:
        return max(fallback, (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds())
    except (ValueError, TypeError, OverflowError):
        return fallback


class Downloader:
    def __init__(self, out, eva, client, key, pause, offline=False):
        self.out, self.eva, self.client, self.key = out, eva, client, key
        self.pause, self.offline = pause, offline
        self.pacer = RequestPacer(pause)
        self.receipts = []
        self.warnings = []

    def post(self, kind, a, b):
        payload = {'stopPlaceOrStation': {'evaNumbers': [self.eva],
                                           'boardConfigurations': ['NONE']},
                   'timeWindow': {'timeStart': iso(a), 'timeEnd': iso(b)},
                   'maxEntriesPerTransportType': LIMIT, 'maxViaStops': 3,
                   'languages': ['deu']}
        # Raw cache is tied to exact request parameters, not just the hour label.
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]
        name = f'{kind}_{a:%Y%m%dT%H%MZ}_{b:%Y%m%dT%H%MZ}_{digest}.json'
        path = self.out / 'raw' / name
        cached = path.exists()
        if cached:
            raw = path.read_bytes()
        elif self.offline:
            raise RuntimeError(f'Missing cached response: {name}')
        else:
            req = Request(f'{BASE}/{kind}', data=json.dumps(payload).encode(),
                          headers={'DB-Client-Id': self.client, 'DB-Api-Key': self.key,
                                   'Content-Type': 'application/json', 'Accept': 'application/json'},
                          method='POST')
            for attempt in range(5):
                try:
                    self.pacer.before_request()
                    with urlopen(req, timeout=45) as res:
                        raw = res.read()
                    break
                except HTTPError as exc:
                    if exc.code in (401, 403):
                        raise RuntimeError(f'HTTP {exc.code}: check credentials and OpenBoards subscription') from None
                    if exc.code not in (429, 500, 502, 503, 504) or attempt == 4:
                        raise RuntimeError(f'HTTP {exc.code} for {kind} {iso(a)}–{iso(b)}; check API product/request') from None
                    retry = exc.headers.get('Retry-After', '') if exc.headers else ''
                    delay = retry_seconds(retry, attempt)
                    if delay > 120:
                        raise RuntimeError('Rate limit: retry later; completed windows are cached') from None
                    print(f'HTTP {exc.code}, retry in {delay}s', flush=True)
                    time.sleep(delay)
                except (URLError, TimeoutError):
                    if attempt == 4:
                        raise RuntimeError(f'Network failure: {kind} {iso(a)}') from None
                    time.sleep(2 ** (attempt + 1))
        board = json.loads(raw)
        if not isinstance(board, dict):
            raise ValueError(f'Unexpected API JSON root: {name}')
        meta = board.get('meta') or {}
        entries = board.get(kind)
        if entries is None and isinstance(meta.get('consideredStopPlaces'), list):
            entries = []
        if not isinstance(entries, list):
            raise ValueError(f'Unexpected API response: missing {kind} array in {name}')
        if not cached:
            tmp = path.with_suffix('.tmp')
            tmp.write_bytes(raw)
            tmp.replace(path)
        truncated = meta.get('truncatedTransportTypes') or []
        # Also subdivide if a category hits the limit, even without an explicit truncation flag.
        per_type = Counter(text((e.get('transport') or {}).get('type')) for e in entries)
        saturated = bool(truncated) or any(n >= LIMIT for n in per_type.values())
        self.receipts.append({'endpoint': kind, 'start': iso(a), 'end': iso(b),
                              'file': name, 'sha256': hashlib.sha256(raw).hexdigest(),
                              'entries': len(entries), 'saved_utc': iso(datetime.fromtimestamp(path.stat().st_mtime, UTC)), 'truncated_types': truncated,
                              'subdivided': saturated, 'cached': cached})
        print(f'{kind:10} {a:%m-%d %H:%M}–{b:%H:%M} UTC: {len(entries)}' +
              (' (splitting)' if saturated else ''), flush=True)
        if saturated:
            if (b-a).total_seconds() <= 60:
                raise RuntimeError(f'Truncated even at one-minute resolution: {name}')
            mid = a + (b-a)/2
            return self.post(kind, a, mid) + self.post(kind, mid, b)
        names = {}
        for s in board.get('stopPlaces') or []:
            ns = s.get('localizedNames') or []
            n = next((x.get('name') for x in ns if x.get('language') == 'deu'), None)
            if not n and ns:
                n = ns[0].get('name')
            names[text(s.get('evaNumber'))] = n or ''
        return [(kind, e, names, name) for e in entries]


def extract(records, eva, start, end, zone):
    events, issues = {}, []
    def issue(reason, source, jid='', kind=''):
        issues.append(dict(reason=reason, source_file=source, journey_id=jid, event_kind=kind))
    for kind, e, names, source in records:
        if text(e.get('evaNumber')) != eva:
            continue
        tr = e.get('transport') or {}
        ji = e.get('journeyInfo') or {}
        jid = text(e.get('journeyId'))
        cat, line = text(tr.get('category')), text((tr.get('line') or {}).get('name'))
        number = text(tr.get('journeyNumber'))
        try:
            planned, reported = dt(e.get('timeSchedule')), dt(e.get('time'))
        except (ValueError, TypeError, AttributeError):
            issue('invalid_timestamp', source, jid, kind)
            continue
        if not jid or not planned:
            issue('missing_journey_id_or_scheduled_time', source, jid, kind)
            continue
        def ref(v):
            k = text((v or {}).get('evaNumber'))
            return names.get(k) or k
        row = dict(event_kind=kind, journey_id=jid, eva=eva, category=cat, line=line,
                   train_number=number, label=text(tr.get('label')),
                   target_service=target(cat,line), transport_type=text(tr.get('type')),
                   origin=ref(ji.get('origin')), destination=ref(ji.get('destination')),
                   direction=' / '.join((tr.get('direction') or {}).get('texts') or []),
                   via=' | '.join(ref(v) for v in tr.get('via') or []),
                   scheduled_time=iso(planned.astimezone(zone)),
                   reported_time=iso(reported.astimezone(zone)) if reported else '',
                   time_type=text(e.get('timeType')),
                   reported_minus_scheduled_min=(reported-planned).total_seconds()/60 if reported else '',
                   scheduled_platform=text((e.get('platformSchedule') or {}).get('name')),
                   reported_platform=text((e.get('platform') or {}).get('name')),
                   cancelled=e.get('cancelled') is True, journey_cancelled=ji.get('journeyCancelled') is True,
                   additional=e.get('additional') is True, no_passenger_change=e.get('noPassengerChange') is True,
                   replacement=bool(tr.get('replacementTransport')),
                   scheduled_in_day=start <= planned < end,
                   reported_in_day=bool(reported and start <= reported < end), source_file=source)
        key = (kind, jid, planned)
        if key in events:
            old = events[key]
            # Never silently collapse conflicting versions of the same event.
            if any(old[k] != row[k] for k in ('scheduled_platform','reported_platform','reported_time','time_type','cancelled','journey_cancelled','category','line','train_number')):
                issue('conflicting_duplicate_event', source, jid, kind)
                old['conflicting_duplicate'] = True
            continue
        row['conflicting_duplicate'] = False
        events[key] = row
    return list(events.values()), issues


EVENT_FIELDS = ('event_kind journey_id eva category line train_number label target_service transport_type origin destination direction via scheduled_time reported_time time_type reported_minus_scheduled_min scheduled_platform reported_platform cancelled journey_cancelled additional no_passenger_change replacement scheduled_in_day reported_in_day source_file conflicting_duplicate').split()
CALL_FIELDS = ('train_id journey_id target_service category line train_number origin destination arrival_via departure_via scheduled_arrival scheduled_departure scheduled_arrival_min scheduled_departure_min scheduled_dwell_min arrival_platform_schedule departure_platform_schedule planned_platform arrival_reported_platform departure_reported_platform arrival_reported_time departure_reported_time arrival_time_type departure_time_type arrival_reported_delay_min departure_reported_delay_min arrival_cancelled departure_cancelled journey_cancelled additional replacement scheduled_in_day reported_in_day initial_occupancy cross_midnight status review_reason arrival_source departure_source').split()


def make_calls(events, start, end):
    by_journey = defaultdict(list)
    for e in events:
        by_journey[e['journey_id']].append(e)
    calls = []
    for jid, rows in sorted(by_journey.items()):
        arr = [e for e in rows if e['event_kind']=='arrivals']
        dep = [e for e in rows if e['event_kind']=='departures']
        # A journey with multiple calls at the station needs explicit review.
        # Keep each event, rather than inventing a potentially false arrival/departure match.
        multiple = len(arr)>1 or len(dep)>1
        pairs = ([(a,{}) for a in arr]+[({},d) for d in dep]) if multiple else [(arr[0] if arr else {},dep[0] if dep else {})]
        for i,(a,d) in enumerate(pairs,1):
            ref = d or a
            at, de = dt(a.get('scheduled_time')), dt(d.get('scheduled_time'))
            in_day = any(x.get('scheduled_in_day',False) for x in (a,d))
            reported_day = any(x.get('reported_in_day',False) for x in (a,d))
            overlap = bool(at and de and at < end and de > start)
            if not (in_day or reported_day or overlap):
                continue
            ap, dp = a.get('scheduled_platform',''), d.get('scheduled_platform','')
            pa,pd = platform(ap),platform(dp)
            p = pa if pa is not None else pd
            reasons = []
            if multiple: reasons.append('multiple_events_for_journey')
            if not at: reasons.append('missing_arrival_or_originating')
            if not de: reasons.append('missing_departure_or_terminating')
            if at and de and de < at: reasons.append('departure_before_arrival')
            if at and de and de == at: reasons.append('zero_scheduled_dwell')
            if ap and dp and (pa != pd or (pa is None and ap != dp)):
                p = None; reasons.append('conflicting_planned_platforms')
            elif at and de and (pa is None or pd is None):
                reasons.append('missing_one_planned_platform')
            if p is None: reasons.append('unknown_planned_platform')
            if a and d and any(a.get(k)!=d.get(k) for k in ('category','line','train_number','target_service')):
                reasons.append('arrival_departure_identity_conflict')
            if any(x.get('conflicting_duplicate') for x in (a,d)): reasons.append('conflicting_duplicate_event')
            cancelled = any(x.get('cancelled') or x.get('journey_cancelled') for x in (a,d))
            additional = any(x.get('additional') for x in (a,d))
            replacement = any(x.get('replacement') for x in (a,d))
            if cancelled: reasons.append('cancelled_event')
            if additional: reasons.append('additional_event')
            if replacement: reasons.append('replacement_transport')
            service = ref['target_service'] or a.get('target_service','')
            if service in ('RE','RB'): reasons.append('regional_line_missing_or_unrecognized')
            if not service: status='outside_service_scope'
            elif p is not None and p not in (2,3,4,5) and 'conflicting_planned_platforms' not in reasons and 'conflicting_duplicate_event' not in reasons: status='outside_platform_scope'
            elif reasons: status='review'
            elif not in_day and not overlap: status='reported_day_only'
            elif p not in (2,3,4,5): status='outside_platform_scope'
            else: status='candidate'
            def minute(t): return (t-start).total_seconds()/60 if t else ''
            identifier = hashlib.sha256(f'{jid}|{i}|{iso(at)}|{iso(de)}'.encode()).hexdigest()[:20]
            calls.append(dict(train_id=identifier,journey_id=jid,target_service=service,category=ref['category'],line=ref['line'],train_number=ref['train_number'],origin=ref['origin'],destination=ref['destination'],arrival_via=a.get('via',''),departure_via=d.get('via',''),scheduled_arrival=a.get('scheduled_time',''),scheduled_departure=d.get('scheduled_time',''),scheduled_arrival_min=minute(at),scheduled_departure_min=minute(de),scheduled_dwell_min=(de-at).total_seconds()/60 if at and de else '',arrival_platform_schedule=ap,departure_platform_schedule=dp,planned_platform=p if p is not None else '',arrival_reported_platform=a.get('reported_platform',''),departure_reported_platform=d.get('reported_platform',''),arrival_reported_time=a.get('reported_time',''),departure_reported_time=d.get('reported_time',''),arrival_time_type=a.get('time_type',''),departure_time_type=d.get('time_type',''),arrival_reported_delay_min=a.get('reported_minus_scheduled_min',''),departure_reported_delay_min=d.get('reported_minus_scheduled_min',''),arrival_cancelled=a.get('cancelled',''),departure_cancelled=d.get('cancelled',''),journey_cancelled=any(x.get('journey_cancelled') for x in (a,d)),additional=additional,replacement=replacement,scheduled_in_day=in_day,reported_in_day=reported_day,initial_occupancy=bool(at and de and at<start<de),cross_midnight=bool(at and de and at<end<de),status=status,review_reason=';'.join(reasons),arrival_source=a.get('source_file',''),departure_source=d.get('source_file','')))
    return sorted(calls,key=lambda x:(x['scheduled_arrival'] or x['scheduled_departure'],x['train_id']))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--date', required=True, type=date.fromisoformat, help='Local calendar day YYYY-MM-DD')
    p.add_argument('--eva', default=EVA)
    p.add_argument('--output', type=Path, help='Default: data/timetable/openboards/YYYY-MM-DD')
    p.add_argument('--window-minutes', type=int, default=60)
    p.add_argument('--padding-hours', type=int, default=6, help='Capture adjacent hours for cross-midnight/late trains')
    p.add_argument('--pause', type=float, default=1.0, help='Minimum seconds between HTTP attempt starts (default 1; hard minimum 0.2, including retries)')
    p.add_argument('--offline', action='store_true', help='Reprocess existing raw cache without credentials')
    args=p.parse_args()
    if not 1<=args.window_minutes<=480 or not 0<=args.padding_hours<=24 or not math.isfinite(args.pause) or args.pause<0:
        p.error('Invalid window, padding or pause')
    if not re.fullmatch(r'\d{7}',args.eva): p.error('EVA must have seven digits')
    try: zone=ZoneInfo('Europe/Berlin')
    except ZoneInfoNotFoundError: p.error('Install timezone data: python -m pip install tzdata')
    start=datetime.combine(args.date,datetime.min.time(),zone).astimezone(UTC)
    end=datetime.combine(args.date+timedelta(days=1),datetime.min.time(),zone).astimezone(UTC)
    out=args.output or Path('data/timetable/openboards')/args.date.isoformat()
    out.mkdir(parents=True,exist_ok=True); (out/'raw').mkdir(exist_ok=True)
    client=key=''
    if not args.offline:
        client=os.getenv('DB_CLIENT_ID') or getpass.getpass('DB Client ID: ')
        key=os.getenv('DB_API_KEY') or getpass.getpass('DB API Key: ')
        if not client or not key: p.error('Both credentials are required')
    dl=Downloader(out,args.eva,client,key,args.pause,args.offline)
    if not args.offline:
        print(f'HTTP pacing: >= {dl.pacer.interval:g}s between attempts (limit 10/s; sequential requests)', flush=True)
    begin=start-timedelta(hours=args.padding_hours); finish=end+timedelta(hours=args.padding_hours)
    manifest={'api':BASE,'eva':args.eva,'date':args.date.isoformat(),'timezone':'Europe/Berlin','day_start':iso(start.astimezone(zone)),'day_end':iso(end.astimezone(zone)),'capture_start':iso(begin),'capture_end':iso(finish),'window_minutes':args.window_minutes,'status':'incomplete','started_utc':iso(datetime.now(UTC))}
    dump(out/'manifest.json',manifest)
    try:
        records=[]; a=begin
        while a<finish:
            b=min(finish,a+timedelta(minutes=args.window_minutes))
            for kind in ('arrivals','departures'):
                records.extend(dl.post(kind,a,b))
            a=b
        events,issues=extract(records,args.eva,start,end,zone)
        calls=make_calls(events,start,end)
        selected=[c for c in calls if c['target_service']]
        candidates=[c for c in selected if c['status']=='candidate']
        review=[c for c in selected if c['status']=='review']
        write_csv(out/'all_events.csv',events,EVENT_FIELDS)
        write_csv(out/'all_station_calls.csv',calls,CALL_FIELDS)
        write_csv(out/'target_calls.csv',selected,CALL_FIELDS)
        write_csv(out/'candidates_gleis_2_5.csv',candidates,CALL_FIELDS)
        write_csv(out/'needs_review.csv',review,CALL_FIELDS)
        write_csv(out/'event_issues.csv',issues,['reason','source_file','journey_id','event_kind'])
        summary={'station_events':len(events),'station_calls':len(calls),'target_calls':len(selected),'target_by_service':dict(Counter(c['target_service'] for c in selected)),'target_by_status':dict(Counter(c['status'] for c in selected)),'unclassified_regional_events':sum(e['target_service'] in ('RE','RB') for e in events),'candidate_count':len(candidates),'review_count':len(review),'event_issue_count':len(issues),'target_scheduled_in_day':sum(c['scheduled_in_day'] for c in selected),'target_reported_in_day':sum(c['reported_in_day'] for c in selected),'candidate_by_platform':dict(Counter(str(c['planned_platform']) for c in candidates))}
        summary['http_rate_limit'] = dl.pacer.stats()
        manifest.update(status='retrieved_for_review' if events else 'empty_response_review_required',summary=summary)
        dump(out/'summary.json',summary)
        print(json.dumps(summary,ensure_ascii=False,indent=2)); print(f'Files: {out.resolve()}')
        return 0 if events and selected else 2
    except (RuntimeError, ValueError, OSError) as exc:
        # API errors contain only status/window, never authorization headers.
        manifest['error']=str(exc)
        print(f'ERROR: {exc}',file=sys.stderr)
        return 1
    finally:
        manifest['requests']=dl.receipts; manifest['finished_utc']=iso(datetime.now(UTC))
        manifest['http_rate_limit']=dl.pacer.stats()
        dump(out/'manifest.json',manifest)


if __name__=='__main__':
    raise SystemExit(main())
