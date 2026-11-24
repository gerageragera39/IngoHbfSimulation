#!/usr/bin/env python3
"""Download external originals into assets/external; Python stdlib only."""
import hashlib, json, pathlib, urllib.request, urllib.parse, sys
root=pathlib.Path(__file__).resolve().parent
out=root/'assets'/'external'; out.mkdir(parents=True,exist_ok=True)
manifest=json.loads((root/'sources'/'asset_manifest.json').read_text(encoding='utf-8'))
failed=[]
for item in manifest:
    url=item.get('url')
    if not url:
        name=item['commons_file'].replace(' ','_')
        h=hashlib.md5(name.encode()).hexdigest()
        url='https://upload.wikimedia.org/wikipedia/commons/'+h[0]+'/'+h[:2]+'/'+urllib.parse.quote(name)
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'IngolstadtHbfUniversityPresentation/1.0 (academic slide preparation)'})
        with urllib.request.urlopen(req,timeout=35) as res: data=res.read()
        ok=data.startswith(b'%PDF-') if item['kind']=='pdf' else data.startswith(b'\xff\xd8\xff')
        if not ok: raise ValueError('Unexpected format; not the requested PDF/JPEG')
        p=out/item['filename'];p.write_bytes(data);print(f'OK {p.name}: {len(data):,} bytes')
    except Exception as e:
        failed.append(item['filename']); print(f'FAILED {item["filename"]}: {e}\n  Open manually: {item.get("page",url)}',file=sys.stderr)
print(f'{len(manifest)-len(failed)}/{len(manifest)} downloaded. Verify contents and licenses before using.')
if failed: sys.exit(1)
