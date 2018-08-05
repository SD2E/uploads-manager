# Ingest File on Upload

This Reactor responds to upload events by copying the uploaded file from S3 to
the destination configured in the settings document. No path remapping is done.
The Reactor also makes a couple of attempts to grant `READ`  to `world` on the
file and any directories created as a consequence of the copy. Finally, it
messages one or more downstream Reactors with the agave-canonical form of the
file path for additional processing.

# Example inbound message

```json
{"uri": "s3://uploads/emerald/201809/protein.png"}
```

## Example outbound message

```json
{"uri": "agave://data-sd2e-community/uploads/emerald/201809/protein.png"}
```
