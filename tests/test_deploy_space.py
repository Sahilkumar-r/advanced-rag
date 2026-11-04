import importlib.util
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location("deploy_space", Path(__file__).resolve().parent.parent / "scripts" / "deploy_space.py")
ds = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ds)

ENV = {"GROQ_API_KEY": "g", "GEMINI_API_KEY": "m", "OPENAI_API_KEY": "must-not-be-sent", "HF_TOKEN": "must-not-be-sent", "DEMO_ADMIN_PASSWORD": "a" * 12, "JWT_SECRET": "local-secret-not-reused"}


class FakeApi:
    def __init__(self, exists, stages=("BUILDING", "RUNNING")):
        self.exists, self.stages, self.secrets, self.uploaded, self.created = exists, list(stages), {}, None, None

    def whoami(self):
        return {"name": "someone"}

    def repo_exists(self, repo, repo_type=None):
        return self.exists

    def create_repo(self, repo, **kw):
        self.created = (repo, kw)

    def upload_folder(self, folder_path, repo_id, **kw):
        self.uploaded = sorted(p.name for p in Path(folder_path).iterdir())

    def add_space_secret(self, repo, key, value):
        self.secrets[key] = value

    def get_space_runtime(self, repo):
        return SimpleNamespace(stage=self.stages.pop(0) if len(self.stages) > 1 else self.stages[0])


def fake_bundle(dest):
    dest.mkdir(parents=True)
    (dest / "Dockerfile").write_text("FROM scratch")
    return ["Dockerfile"]


def test_new_space_gets_provider_keys_demo_passwords_and_a_fresh_jwt_but_never_openai_or_the_hf_token():
    api = FakeApi(exists=False)
    r = ds.deploy(api, "ragx", False, ENV, bundle_fn=fake_bundle, poll_s=0)
    assert set(api.secrets) == {"GROQ_API_KEY", "GEMINI_API_KEY", "DEMO_ADMIN_PASSWORD", "JWT_SECRET"}
    assert api.secrets["JWT_SECRET"] != ENV["JWT_SECRET"] and len(api.secrets["JWT_SECRET"]) >= 32
    assert "OPENAI_API_KEY" not in api.secrets and "HF_TOKEN" not in api.secrets
    assert r["new"] and r["stage"] == "RUNNING" and api.created[1]["space_sdk"] == "docker" and api.created[1]["private"] is False and api.uploaded == ["Dockerfile"]


def test_updating_an_existing_space_keeps_its_jwt_secret_unless_asked_to_rotate():
    api = FakeApi(exists=True)
    ds.deploy(api, "ragx", True, ENV, bundle_fn=fake_bundle, wait=False)
    assert "JWT_SECRET" not in api.secrets and api.created[1]["private"] is True
    api2 = FakeApi(exists=True)
    ds.deploy(api2, "ragx", True, ENV, bundle_fn=fake_bundle, wait=False, rotate_jwt=True)
    assert "JWT_SECRET" in api2.secrets


def test_a_failed_build_is_reported_not_waited_on_forever():
    r = ds.deploy(FakeApi(exists=True, stages=("BUILDING", "BUILD_ERROR")), "ragx", False, ENV, bundle_fn=fake_bundle, poll_s=0)
    assert r["stage"] == "BUILD_ERROR"
