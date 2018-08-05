# Ingest File on Upload

This Reactor responds to upload events by copying the uploaded file from S3 to
the destination configured in the settings document. No path remapping is done.
The Reactor also makes a single attempt to grant `READ`  to `world` on the file
and any directories created as a consequence of it being copied. Finally, it
messages one or more downstream Reactors with the agave-canonical form of the
file path for additional processing.

# Example inbound message

```json
{}
```

## Example outbound message

```json
{"uri": "agave://data-sd2e-community/uploads/transcriptic/201808/r1bbktv6x4xke/bigdata.txt"}
```
