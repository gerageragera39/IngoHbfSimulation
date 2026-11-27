#!/usr/bin/env python3
"""Platform utilization and reassignment analysis; run from repository root."""
from __future__ import annotations

import argparse
import fnmatch
import math
import statistics as st
from collections import defaultdict, Counter
from pathlib import Path

import analyze_results as ar

PLATFORMS = ar.PLATFORMS


def configuration(rows):
    configs = {ar.transfer_configuration(r) for r in rows}
    ar.require(len(configs) == 1, 'Mixed transfer settings within a pair')
    return configs.pop()


def label(config):
    mode, cross, same = config
    return f'{mode}_T{cross:g}' + (f'_S{same:g}' if mode == 'MATRIX' else '')


def metrics(rows, horizon):
    result = []
    passenger_available = "passenger_induced_delay_min" in rows[0]
    counts = Counter((int(r['planned_platform']), int(r['assigned_platform']))
                     for r in rows)
    by_platform = defaultdict(list)
    for row in rows:
        by_platform[int(row['assigned_platform'])].append(row)
    for p in PLATFORMS:
        trains = by_platform[p]
        intervals = [(float(r['platform_arrival']), float(r['actual_departure']))
                     for r in trains]
        ar.require(all(0 <= a <= d <= horizon + ar.TOL for a, d in intervals),
                   f'Gleis {p}: invalid occupancy interval')
        intervals.sort()
        ar.require(all(b[0] >= a[1] - ar.TOL
                       for a, b in zip(intervals, intervals[1:])),
                   f'Gleis {p}: overlapping trains')
        busy = sum(d - a for a, d in intervals)
        ar.require(busy <= horizon + ar.TOL, f'Gleis {p}: utilization exceeds 100%')
        result.append(dict(
            platform=p, train_count=len(trains), busy_min=busy,
            utilization_pct=100 * busy / horizon if horizon else None,
            mean_occupancy_min=busy / len(trains) if trains else None,
            passenger_induced_delay_min=(
                sum(float(r['passenger_induced_delay_min']) for r in trains)
                if passenger_available else None
            ),
        ))
    return result, counts


def observation_horizon(runs):
    return max(float(row['actual_departure']) for rows in runs for row in rows)


def run_metrics(rows, platforms, counts):
    utilization = [p['utilization_pct'] for p in platforms]
    available = utilization[0] is not None
    categories = Counter()
    for (planned, assigned), count in counts.items():
        categories[ar.assignment_category(planned, assigned)] += count
    passenger_delays = [p['passenger_induced_delay_min'] for p in platforms]
    return dict(
        train_count=len(rows),
        last_departure_min=observation_horizon([rows]),
        mean_utilization_pct=st.mean(utilization) if available else None,
        utilization_range_pp=max(utilization) - min(utilization) if available else None,
        utilization_sd_pp=st.pstdev(utilization) if available else None,
        same_island_reassignments=categories['Same island'],
        cross_island_reassignments=categories['Cross island'],
        total_station_delay_min=sum(float(r['station_delay_min']) for r in rows),
        passenger_induced_delay_min=(
            sum(passenger_delays) if passenger_delays[0] is not None else None
        ),
    )


def save(path, rows):
    ar.save_csv(path, rows, list(rows[0]))


def charts(platform_summary, run_summary, transfer_summary, output):
    import matplotlib.pyplot as plt
    configs = sorted({r['configuration'] for r in platform_summary})
    for config in configs:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        for i, policy in enumerate(ar.POLICIES):
            rows = sorted((r for r in platform_summary
                           if r['configuration'] == config and r['policy'] == policy),
                          key=lambda r: r['platform'])
            ax.bar([p + (i - .5) * .36 for p in PLATFORMS],
                   [r['mean_utilization_pct'] for r in rows], .36, label=policy)
        ax.set(xticks=PLATFORMS, xlabel='Gleis', ylabel='Mean utilization (%)',
               ylim=(0, 100), title=f'Platform utilization â€” {config}')
        ax.legend()
        fig.tight_layout()
        fig.savefig(output / f'utilization_{config}.png', dpi=160)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(5.5, 4.5))
        cells = {(r['planned_platform'], r['assigned_platform']): r['mean_train_count']
                 for r in transfer_summary
                 if r['configuration'] == config and r['policy'] == 'GREEDY'}
        matrix = [[cells[p, q] for q in PLATFORMS] for p in PLATFORMS]
        im = ax.imshow(matrix)
        for i, p in enumerate(PLATFORMS):
            for j, q in enumerate(PLATFORMS):
                ax.text(j, i, f'{matrix[i][j]:.1f}', ha='center', va='center',
                        color='white' if matrix[i][j] < im.norm.vmax / 2 else 'black')
        ax.set(xticks=range(4), yticks=range(4), xticklabels=PLATFORMS,
               yticklabels=PLATFORMS, xlabel='Assigned Gleis', ylabel='Planned Gleis',
               title=f'GREEDY assignments â€” {config}')
        fig.colorbar(im, ax=ax, label='Mean trains per scenario')
        fig.tight_layout()
        fig.savefig(output / f'assignments_{config}.png', dpi=160)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, policy in enumerate(ar.POLICIES):
        values = [st.mean(r['utilization_range_pp'] for r in run_summary
                          if r['configuration'] == c and r['policy'] == policy)
                  for c in configs]
        ax.bar([j + (i - .5) * .36 for j in range(len(configs))], values, .36, label=policy)
    ax.set(xticks=range(len(configs)), xticklabels=configs,
           ylabel='Mean utilization range (percentage points)',
           title='Platform load imbalance (lower is better)')
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / 'load_imbalance.png', dpi=160)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, default=Path('Ingo/results'))
    ap.add_argument('--output', type=Path, default=Path('analysis/output/P3_UTILIZATION'))
    ap.add_argument('--scenario-glob', default='P2_MATRIX_T*')
    ap.add_argument('--expected-trains', type=int, default=120)
    ap.add_argument('--expected-scenarios', type=int, default=10,
                    help='Expected paired scenarios per configuration')
    ap.add_argument('--expected-configurations', type=int, default=3)
    ap.add_argument('--no-plots', action='store_true')
    args = ap.parse_args()

    groups = defaultdict(dict)
    for path in sorted(args.input.glob('train_results_*.csv')):
        match = ar.FILENAME_RE.fullmatch(path.name)
        if match:
            policy, scenario, seed = match.groups()
            if fnmatch.fnmatchcase(scenario, args.scenario_glob):
                groups[(scenario, int(seed))][policy] = path
    ar.require(bool(groups), 'No matching results')

    pairs = []
    seeds = defaultdict(set)
    for (scenario, seed), paths in sorted(groups.items()):
        # Reuse the existing compatibility, delay, pairing and passenger checks.
        ar.analyse_scenario((scenario, seed), paths, args.input, args.expected_trains)
        runs = {p: ar.load_csv(paths[p]) for p in ar.POLICIES}
        config = configuration(runs['FIXED_DB'] + runs['GREEDY'])
        c = label(config)
        ar.require(seed not in seeds[c], f'{c}: repeated seed {seed}')
        seeds[c].add(seed)
        pairs.append((scenario, seed, c, runs))
    ar.require(len(seeds) == args.expected_configurations,
               f'Expected {args.expected_configurations} configurations, got {len(seeds)}')
    for c, s in seeds.items():
        ar.require(len(s) == args.expected_scenarios,
                   f'{c}: expected {args.expected_scenarios} scenarios, got {len(s)}')
    ar.require(all(s == next(iter(seeds.values())) for s in seeds.values()),
               'Different seed sets across configurations')

    # One common observation window for all selected runs; do not use 500-min stop time.
    horizon = observation_horizon(rows for _, _, _, runs in pairs for rows in runs.values())
    ar.require(math.isfinite(horizon) and horizon > 0, 'Invalid observation horizon')
    platform_rows, run_rows, transfer_rows = [], [], []
    for scenario, seed, config, runs in pairs:
        for policy, rows in runs.items():
            base = dict(configuration=config, scenario_id=scenario,
                        scenario_seed=seed, policy=policy, observation_min=horizon)
            platforms, counts = metrics(rows, horizon)
            platform_rows.extend(dict(base, **p) for p in platforms)
            run_rows.append(dict(base, **run_metrics(rows, platforms, counts)))
            transfer_rows.extend(dict(base, planned_platform=p, assigned_platform=q,
                                      train_count=counts[p, q])
                                 for p in PLATFORMS for q in PLATFORMS)

    platform_summary, run_summary, transfer_summary = [], [], []
    for c in sorted(seeds):
        for policy in ar.POLICIES:
            rs = [r for r in run_rows if r['configuration'] == c and r['policy'] == policy]
            base = dict(configuration=c, policy=policy, scenarios=len(rs), observation_min=horizon)
            fields = ('mean_utilization_pct', 'utilization_range_pp', 'utilization_sd_pp',
                      'same_island_reassignments', 'cross_island_reassignments',
                      'total_station_delay_min', 'passenger_induced_delay_min')
            # Keep field names explicit: values here are averages across scenarios.
            summary = dict(base, **{k: st.mean(r[k] for r in rs) for k in fields})
            run_summary.append(summary)
            for p in PLATFORMS:
                ps = [r for r in platform_rows if r['configuration'] == c and
                      r['policy'] == policy and r['platform'] == p]
                n = sum(r['train_count'] for r in ps)
                platform_summary.append(dict(base, platform=p,
                    mean_train_count=st.mean(r['train_count'] for r in ps),
                    mean_utilization_pct=st.mean(r['utilization_pct'] for r in ps),
                    mean_busy_min=st.mean(r['busy_min'] for r in ps),
                    pooled_mean_occupancy_min=sum(r['busy_min'] for r in ps)/n if n else '',
                    mean_passenger_induced_delay_min=st.mean(r['passenger_induced_delay_min'] for r in ps)))
            for p in PLATFORMS:
                for q in PLATFORMS:
                    ts = [r['train_count'] for r in transfer_rows if r['configuration'] == c and
                          r['policy'] == policy and r['planned_platform'] == p and r['assigned_platform'] == q]
                    transfer_summary.append(dict(base, planned_platform=p, assigned_platform=q,
                                                 total_train_count=sum(ts), mean_train_count=st.mean(ts)))

    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in [('platform_by_scenario', platform_rows), ('run_metrics', run_rows),
                       ('assignments_by_scenario', transfer_rows), ('platform_summary', platform_summary),
                       ('policy_summary', run_summary), ('assignment_matrix', transfer_summary)]:
        save(args.output / f'{name}.csv', data)
    if not args.no_plots:
        charts(platform_summary, run_rows, transfer_summary, args.output)
    print(f'Validated {len(pairs)} paired scenarios; common observation: 0â€“{horizon:.2f} min')
    for r in run_summary:
        print(f"{r['configuration']} {r['policy']}: "
              f"utilization={r['mean_utilization_pct']:.2f}%; "
              f"imbalance={r['utilization_range_pp']:.2f} pp; "
              f"same/cross reassignments={r['same_island_reassignments']:.2f}/{r['cross_island_reassignments']:.2f}; "
              f"direct passenger delay={r['passenger_induced_delay_min']:.2f} min")
    print(f'Results saved to: {args.output.resolve()}')


if __name__ == '__main__':
    main()
