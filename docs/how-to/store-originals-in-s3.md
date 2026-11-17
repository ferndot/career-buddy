# Store originals in S3

Use this to keep uploaded resume files and saved documents on an S3 server instead of the data folder.

By default (`CAREER_BUDDY_STORAGE=local`) they are files under `${CAREER_BUDDY_DATA}/objects`. Each upload is stored once as `sources/<sha256>.<ext>`, and the import event in `events.jsonl` records that key as `source_key`.

## Use the bundled server

The optional `storage` profile in `docker-compose.yml` starts [SeaweedFS](https://github.com/seaweedfs/seaweedfs) (Apache-2.0, pinned to `chrislusf/seaweedfs:4.51`) as a separate, unmodified container.

1. Create a file named `.env` next to `docker-compose.yml`. The defaults are placeholders for development only:

   ```bash
   CAREER_BUDDY_STORAGE=s3
   CAREER_BUDDY_S3_ACCESS_KEY=pick-a-key
   CAREER_BUDDY_S3_SECRET_KEY=pick-a-long-secret
   ```

2. Start both containers:

   ```bash
   docker compose --profile storage up --build
   ```

The app reaches the server at `http://s3:8333` with bucket `careers`. The S3 API is also on `127.0.0.1:8333`. Objects live in the `s3-data` Docker volume, not in `./data`.

## Use your own S3 server

Leave the profile off and set these variables for the app:

- `CAREER_BUDDY_STORAGE=s3`
- `CAREER_BUDDY_S3_ENDPOINT`
- `CAREER_BUDDY_S3_BUCKET`
- `CAREER_BUDDY_S3_ACCESS_KEY`
- `CAREER_BUDDY_S3_SECRET_KEY`
- `CAREER_BUDDY_S3_REGION` (optional, default `us-east-1`)

Any S3 API works, such as [MinIO](https://min.io). The bucket is created on startup if it is missing.

## Run the S3 test

`tests/test_s3_minio_integration.py` runs against a real S3 server when the variables above are set. Otherwise it is skipped.
