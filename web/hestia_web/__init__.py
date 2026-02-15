"""hestia_web package.

Note: don't re-export the Flask `app` object here.
Doing so breaks `import hestia_web.app` because dotted imports resolve attributes
on the package first (and `hestia_web.app` would become the Flask instance).

Gunicorn should target `hestia_web.app:app`.
"""

__all__ = []
