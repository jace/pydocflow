.. Docflow documentation master file, created by
   sphinx-quickstart on Sat Apr 30 14:36:55 2011.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Docflow's documentation!
===================================

This is the documentation for version |version|, generated |today|.

.. toctree::
   :maxdepth: 2

.. contents::

Introduction
------------

Docflow is an implementation of document workflows in Python. A workflow
defines `states` and `transitions`. A state is an “end point” associated with
a document. A transition is a path from one state to another state
(unidirectional). Docflow was inspired by `repoze.workflow`_ but aspires
to be a framework-independent implementation.

A `document` in Docflow is any Python object. The document's workflow is
defined separately from the document. This is a useful distinction in MVC or
MTV-based web applications where the model is kept distinct from the view.
The model is expected to be a dumb container of data while the view contains
business logic. Workflows sit between view and models, controlling the view's
view of the model.

Usage
-----

Documents can be defined like any other Python object::

  >>> class MyDocument:
  ...     def __init__(self):
  ...         self.status = 0
  ...
  ... doc1 = MyDocument()

Documents can be simple dictionaries::

  >>> doc2 = {'title': 'My Document', 'status': 0}

Or complex entities such as SQLAlchemy ::

  >>> from sqlalchemy import Column, Integer, String
  >>> from sqlalchemy.ext.declarative import declarative_base
  >>> Base = declarative_base()
  >>> class DatabaseDocument(Base):
  ...     __tablename__ = 'document'
  ...     id = Column(Integer, primary_key=True)
  ...     title = Column(String(200))
  ...     status = Column(Integer)
  ...
  >>> doc3 = DatabaseDocument()

The important part is that the object must have an attribute or key that
holds the current state, like ``status`` in all three examples. The state
value can be any hashable Python object, typically an integer or string. The
workflow defines all possible states for this document, the value that
represents this state, and the transitions between states::

  from docflow import DocumentWorkflow, WorkflowState, WorkflowStateGroup

  class MyDocumentWorkflow(DocumentWorkflow):
      """
      Workflow for MyDocument
      """

      # Attribute in MyDocument to store status in.
      # Use ``state_key`` if MyDocument is a dictionary,
      # as is typical with NoSQL JSON-based databases.
      state_attr = 'status'

      # Define a state. First parameter is the state tracking value,
      # stored in state_attr.
      draft     = WorkflowState(0, title="Draft",     description="Only owner can see it")
      pending   = WorkflowState(1, title="Pending",   description="Pending review")
      published = WorkflowState(2, title="Published", description="Published")
      withdrawn = WorkflowState(3, title="Withdrawn", description="Withdrawn by owner")
      rejected  = WorkflowState(4, title="Rejected",  description="Rejected by reviewer")

      # Define a state group
      not_published = WorkflowStateGroup([0, 1], title="Not Published")

      def permissions(self, context=None):
          """
          Return permissions available to current user. A permission can be any hashable token.
          """
          if context and context['is_admin']:
              return ['can_publish']
          else:
              return []

      # Define a transition. There can be multiple transitions connecting any two states.
      # Parameters: newstate, permission, title, description
      @draft.transition(pending, None, title='Submit')
      def submit(self, context=None):
          """
          Change workflow state from draft to pending.
          """
          # Do something here
          # ...
          pass # State will be changed automatically if we don't raise an exception

      @pending.transition(published, 'can_publish', title="Publish")
      def publish(self, context=None):
          """
          Publish the document.
          """
          # Also do something here
          # ...
          pass

Workflows can extend other workflows to add additional states::

  class MyDocumentWorkflowExtraState(MyDocumentWorkflow):
      expired = WorkflowState(5, title="Expired")

Or override settings::

  class MyDocumentWorkflowDict(MyDocumentWorkflow):
      state_attr = None
      state_key = 'status'

Transitions take an optional :attr:`context` parameter. The same context is
provided to the :meth:`~docflow.DocumentWorkflow.permissions` method to
determine if the caller has permission to make the transition. Once a workflow
has been defined, usage is straightforward::

  >>> wf = MyDocumentWorkflow(doc1)
  >>> wf.state is wf.draft
  True
  >>> wf.submit() # Call a transition
  >>> wf.state is wf.pending
  True
  >>> wf.draft() # Check if state is active
  False
  >>> wf.pending()
  True

As a convenience mechanism, workflows can be linked to document classes,
making it easier to retrieve the workflow for a given document::

  class MyDocument(object):
      def __init__(self):
          self.status = 0

  class MyDocumentWorkflow(DocumentWorkflow):
      state_attr = 'status'

  MyDocumentWorkflow.apply_on(MyDocument)

After this, the workflow for a document becomes available with the
:attr:`workflow` method::

  doc = MyDocument()
  wf = doc.workflow()

The :meth:`~docflow.DocumentWorkflow.apply_on` method raises
:class:`~docflow.WorkflowException` if the target class
already has an attribute named :attr:`workflow`.


API Documentation
-----------------

Package :mod:`docflow`
~~~~~~~~~~~~~~~~~~~~~~

.. class:: DocumentWorkflow(document)

    The following attributes and methods must be overriden by subclasses of
    :class:`DocumentWorkflow`.

    .. attribute:: state_attr

        Refers to the attribute on the document that contains the state value.
        Default ``None``.

    .. attribute:: state_key

        If :attr:`state_attr` is ``None``, :attr:`state_key` refers to the
        dictionary key in the document containing the state value. Default
        ``None``.

    .. method:: state_get(document)
    .. method:: state_set(document, value)

        If both :attr:`state_attr` and :attr:`state_key` are ``None``, the
        :meth:`state_get` and :meth:`state_set` methods are called with
        the document as a parameter.

    .. attribute:: state

        Currently active workflow state.

    .. method:: permissions([context])

        Permissions available to caller in the given context, returned
        as a list of tokens.

    .. method:: all_states

        Standard method: returns a dictionary of all states in this workflow.

    .. method:: transitions([context])

        Standard method: returns a dictionary of available transitions out of
        the current state.

    .. method:: apply_on(docclass)

        Class method. Applies this workflow to the specified document class.
        The workflow can then be retrieved by calling the :attr:`workflow` method
        on the document.

.. class:: WorkflowState(value, [title, description])

    Define a workflow state as an attribute on a :class:`DocumentWorkflow`.

    :param value: Value representing this workflow state. Can be any
        hashable Python object. Usually an integer or string
    :param title: Optional title for this workflow state
    :param description: Optional description for this workflow state

    .. method:: transition(tostate, permission, [title, description])

        Decorator for a method on :class:`DocumentWorkflow` that handles the
        transition from this state to another. The decorator will test for
        correct state and permission, and will transition the document's state
        if the method returns without raising an exception.

        The method must take :attr:`context` as its first parameter. The
        context is passed to :meth:`~DocumentWorkflow.permissions` to check
        for permission.

        :param tostate: Destination :class:`WorkflowState`
        :param permission: Token representing permission required to call the
            transition. Must be present in the list returned by
            :meth:`~DocumentWorkflow.permissions`
        :param title: Optional title for this transition
        :param description: Optional description for this transition
        :raises WorkflowTransitionException: If this transition is called
            when in some other state
        :raises WorkflowPermissionException: If :attr:`permission` is not in
            :meth:`~DocumentWorkflow.permissions`

.. class:: WorkflowStateGroup(values, [title, description])

    Like :class:`WorkflowState` but lists more than one value. Useful to
    test for the current state being one of many. For example::
    
        >>> class MyWorkflow(DocumentWorkflow):
        ...     draft = WorkflowState(0, title="Draft")
        ...     pending = WorkflowState(1, title="Pending")
        ...     published = WorkflowState(2, title="Published")
        ...     not_published = WorkflowStateGroup([0, 1], title="Not Published")
        ...
        >>> wf = MyWorkflow(doc)
        >>> wf.draft()
        True
        >>> wf.pending()
        False
        >>> wf.published()
        False
        >>> wf.not_published()
        True

    :class:`WorkflowStateGroup` instances cannot have transitions.

    :param values: Valid values as specified in :class:`WorkflowState`
    :type values: ``list``
    :param title: Optional title for this workflow state
    :param description: Optional description for this workflow state


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _repoze.workflow: http://docs.repoze.org/workflow/
