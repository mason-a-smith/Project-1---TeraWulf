"""Hash delivered files; verify frozen contents with --verify."""
from pathlib import Path
import hashlib,sys
ROOT=Path(__file__).resolve().parents[1]
def included(p):return p.is_file() and '__pycache__' not in p.parts and p.name not in ('MANIFEST.sha256',)
if '--verify' in sys.argv:
    for line in (ROOT/'MANIFEST.sha256').read_text(encoding='utf-8').splitlines():
        digest,relative=line.split('  ',1)
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest,relative
    print('PASS: all manifest hashes match.')
else:
    files=sorted(p for p in ROOT.rglob('*') if included(p))
    (ROOT/'MANIFEST.sha256').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in files),encoding='utf-8')
    print(f'Frozen {len(files)} artifacts.')
    if '--package' in sys.argv:
        import zipfile
        with zipfile.ZipFile(ROOT.parent/'Project1_Final.zip','w',zipfile.ZIP_DEFLATED) as archive:
            for p in files+[ROOT/'MANIFEST.sha256']:
                archive.write(p,Path(ROOT.name)/p.relative_to(ROOT))
        print('Created Project1_Final.zip')
