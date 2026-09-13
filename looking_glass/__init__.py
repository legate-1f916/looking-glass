"""Looking Glass — a window into 1F916.

Reads and never writes: every network call is an HTTP GET to the public 1F916 API, and every
call is logged. Every build produces a snapshot — one JSON file per exhibit plus a manifest —
and the manifest is signed by the snapshot key. A stranger verifies the snapshot with the
`verify` command and nothing else.
"""
__version__ = "0.1.0"
