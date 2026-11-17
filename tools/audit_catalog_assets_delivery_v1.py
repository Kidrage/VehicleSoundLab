"""Independent archive/identity/download audit; no repeat rendering or heard-quality claim."""
import argparse
import hashlib
from pathlib import Path
import shutil
from urllib.request import urlopen

from research_archive_v1 import load, save, sha
from vehicle_controller import recipe,take
from vehicle_controller.native import Bridge


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,args.output/'executed_audit.py')
    repo = Path(__file__).resolve().parents[1]
    report = dict(result='running',goal_complete=False)
    try:
        manifest = load(args.freeze/'manifest.json')
        expected = {row['path'] for row in manifest['files']}
        actual = {p.relative_to(args.freeze).as_posix() for p in args.freeze.rglob('*') if p.is_file() and p != args.freeze/'manifest.json'}
        assert expected == actual
        for row in manifest['files']:
            path = args.freeze/row['path']
            assert path.resolve().is_relative_to(args.freeze.resolve())
            assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256'],row['path']
        base = Path(manifest['base_freeze'])
        assert sha(base/'manifest.json') == manifest['base_manifest_sha256']
        frozen = load(args.freeze/'repo/research/catalog_asset_identity_v1_verification.json')
        assert frozen == load(repo/'research/catalog_asset_identity_v1_verification.json')
        for name,digest in frozen['source_files'].items():
            assert sha(repo/name) == sha(args.freeze/'repo'/name) == digest,name
        for name,digest in load(args.freeze/'evidence/runtime.json').items():
            assert sha(repo/name) == digest,name
        bridge = Bridge(repo)
        assert bridge.sha256 == frozen['bridge_sha256']
        assert bridge.catalog_assets == load(args.freeze/'evidence/catalog-assets.json')
        assert bridge.catalog_assets_sha256 == frozen['catalog_assets_sha256']
        review = args.freeze/'evidence/lifecycle1/review'
        recipe.validate(bridge,load(review/'controller-preset.json'))
        value = take.read(review/'full.take.json',bridge)
        assert value['frames'] == 36*48000 and value['schema'].endswith('/9')
        tracks = load(review/'tracks.json')
        assert len(tracks) == 8
        assert all(sha(review/row['file']) == row['sha256'] for row in tracks)
        url = frozen['published_review']['url']
        with urlopen(url,timeout=5) as response:
            assert response.status == 200 and hashlib.sha256(response.read()).hexdigest() == sha(review/'index.html')
        for name in ('controller-preset.json','full.take.json'):
            with urlopen(url.rsplit('/',1)[0]+'/'+name,timeout=5) as response:
                assert response.status == 200 and hashlib.sha256(response.read()).hexdigest() == sha(review/name)
        for name in ('verification1/report.json','lifecycle1/report.json','ui2/report.json','launch2/report.json','review-web1/verification.json'):
            assert load(args.freeze/'evidence'/name)['result'] == 'passed'
        report.update(result='passed',files=len(expected),bytes=sum(r['bytes'] for r in manifest['files']),
            manifest_sha256=sha(args.freeze/'manifest.json'),base_manifest_exact=True,current_sources_exact=True,
            runtime_459_and_92_catalog_inputs_exact=True,binary_exact=True,published_HTTP_and_downloads_exact=True,
            current_formats_load=True,new_timbre_accepted=False)
    except Exception as error:
        report.update(result='failed',error=repr(error))
        raise
    finally:
        save(args.output/'report.json',report)
    print(report,flush=True)


if __name__ == '__main__':
    main()
