"""Render-call sentinel; validated season state is passed explicitly, never cached."""

# None means load_current validated that no season archive exists.  Only omission
# requests a new disk validation, including for independently called renderers.
SEASON_UNLOADED = object()
