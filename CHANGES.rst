0.3.3
-----

- Bugfix: Instantiating a workflow would clobber the workflow class

0.3.2
-----

- Transition handlers can now connect multiple from/to states
- New: transition_from for specifying a transition in reverse
- New: interactive transitions with form/validate/submit methods
- Python 3 compatibility
- Support for multiple workflows per document class, with workflow names

0.3.1
-----

- Fixed distribution package on PyPI

0.3
---

- States now remember the order in which they were defined, for UI purposes
- Document sorting by workflow state
- Helper method to list available transitions
- Subclasses can now override workflow exceptions
  (for framework-specific Forbidden handlers)


0.2
---

- Workflows now have an ``apply_on`` class method.

0.1
---

- Initial version (alpha)
