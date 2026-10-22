import json
import pytest
from patternforecast import freeze
from patternforecast.common import sha256


def test_confirmation_rejects_changed_sources_thresholds_and_models(tmp_path,monkeypatch):
    config=tmp_path/'config';config.mkdir()
    cache=tmp_path/'cache';(cache/'air').mkdir(parents=True)
    runs=tmp_path/'runs';(runs/'air').mkdir(parents=True)
    source=tmp_path/'source.py';source.write_text('version=1')
    model=runs/'air/model.joblib';model.write_bytes(b'frozen model fixture')
    cuts=cache/'air/cuts.json';cuts.write_text('[1,2,3]')
    for key,value in [('CONFIG',config),('CACHE',cache),('RUNS',runs),('ROOT',tmp_path)]:monkeypatch.setattr(freeze,key,value)
    with pytest.raises(RuntimeError,match='not frozen'):freeze.verify_freeze('air')
    manifest={'source_sha256':{'source.py':sha256(source)},'datasets':{'air':{
        'cuts_sha256':sha256(cuts),'models':{'model':{'model_sha256':sha256(model)}}}}}
    (config/'FROZEN.json').write_text(json.dumps(manifest))
    assert freeze.verify_freeze('air','model')==manifest
    with pytest.raises(RuntimeError,match='Unregistered'):freeze.verify_freeze('air','unknown')
    model.write_bytes(b'changed model')
    with pytest.raises(RuntimeError,match='model changed'):freeze.verify_freeze('air','model')
    model.write_bytes(b'frozen model fixture');cuts.write_text('[9,8,7]')
    with pytest.raises(RuntimeError,match='thresholds changed'):freeze.verify_freeze('air','model')
    cuts.write_text('[1,2,3]');source.write_text('version=2')
    with pytest.raises(RuntimeError,match='source changed'):freeze.verify_freeze('air','model')
