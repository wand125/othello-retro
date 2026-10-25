# Othello Retro Web interfaces and service source

This tree contains the original local reconstruction UI, record player/video UI, simplified public UI, article assets, Cloud Run service code, and the independent Short UI. It contains source and static examples, not a database dump, credentials, production environment settings, usage logs, task records, user videos, or deployment images.

`solver/ui` and `solver/cloud` must remain beside the released Rust/ML source under `solver/`: their path-relative imports and executable/model lookups depend on that layout. `short/` is a sibling of `solver/`.

All command examples below run from the release repository root. This document and its license/dependency companions are installed under `solver/`.

For the local UI, build the Rust executable and install the solver/ML dependencies described by the main release, then run:

```sh
python3 solver/ui/server.py --host 127.0.0.1 --port 8765
```

Weights are separate Release assets; the solver executable must be built from the provided source. The original recorder/video editor additionally needs the optional Mediabunny dependency described in `THIRD_PARTY_WEB.md`; the simplified public app and Short interface do not use it.

The Cloud service entry point is `solver/cloud/app.py`. Configure your own `GOOGLE_CLOUD_PROJECT`, `REGION`, `APP_ROLE`, `WORKER_URL`, `TASK_SERVICE_ACCOUNT`, and optional `API_BACKEND_URL` according to your own deployment. Obtain Google Cloud credentials through your normal runtime identity, not committed files. Python dependencies are in `solver/cloud/requirements.txt`; the solver/ML runtime has additional requirements from the main release. The queue name in this source is `othello-retro`; provision that queue in your own project or adapt it. `MAX_SOLVE_SECONDS`, `GLOBAL_DAILY_JOBS`, and `SESSION_DAILY_JOBS` control limits. No production quota documents, Firestore data, queues, service identities, immutable image names, or environment snapshots are provided. The benchmark-administration helper is optional and expects the separately released benchmark source layout.

For a static Short preview:

```sh
python3 short/preview.py --port 18807
```

This binds only `127.0.0.1` and does not send reconstruction requests to the original public service. To connect an API you control, pass its origin explicitly:

```sh
python3 short/preview.py --port 18807 --backend https://your-service.example
```

Loopback HTTP origins are also accepted for a local development API. The Short UI uses Web Audio synthesis, with wood as the default tone and an existing stored voice preference taking precedence. No external sound recordings are required.

The Short Docker overlay is an optional existing-image workflow: its build takes a caller-supplied base image, copies the three Short assets and adds static routes through `short/install_short.py`. It does not copy arbitrary local application state into the image. No original production image or Cloud project is assumed by its build configuration. This is a source snapshot, not an extraction of the running service image: live Short overlays can add routes to that image. Apply the additive installer in your own image when enabling Short.

Licenses and the article's separate license scope are in `WEB_LICENSES.md`. `WEB_SOURCE_AUDIT.json` lists the source snapshot and stage-only configuration changes. The staged `solver/cloud/build_examples.py` keeps its replay helper but replaces original private video/export/measurement inputs with an explicit `--input` public record file. Ready-to-serve static examples are included and do not need regeneration. There are no copied reference manuscripts or media recordings in this tree.
