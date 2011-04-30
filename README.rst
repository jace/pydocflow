Python Document Workflows
=========================

An implementation of document workflows in Python. Designed for SQLAlchemy but
not dependent upon it.

Note: This is currently just a planning document.

Usage:

1. Define your document the usual way (SQLAlchemy example)::

    Base = base_metadata() # SQLAlchemy base class
    class MyDocument(Base):
        status = Column(Integer)
        email = Column(Unicode(250))
        email_verified = Column(Boolean, default=False)
        ...

2. Define a workflow for this document type::

    from docflow import DocumentWorkflow, WorkflowState, WorkflowStateGroup, WorkflowTransition
    from docflow import TransitionException
    
    class MyDocumentWorkflow(DocumentWorkflow):
        """
        Workflow for MyDocument
        """

        # Attribute in MyDocument to store status in.
        # Use ``state_key`` if MyDocument is a dictionary,
        # as is typical with NoSQL JSON-based databases.
        state_attr = 'status'

        # Define a state. First parameter is the state tracking value,
        # stored in status_attr
        draft = WorkflowState(0, title="Draft", description="Only owner can see it")
        pending = WorkflowState(1, title="Pending", description="Pending review")
        published = WorkflowState(2, title="Published", description="Published")
        withdrawn = WorkflowState(3, title="Withdrawn", description="Withdrawn by owner")
        rejected = WorkflowState(4, title="Rejected", description="Rejected by reviewer")

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

        # Define a transition. There can be multiple transitions connecting any two states, with
        # differing conditions on their use. Parameters: old, new, permission, title, description
        # The state names (as strings) must match the variable names above.
        @draft.transition(pending, None, title="Submit")
        def submit(self, context=None):
            """
            Change workflow state from draft to pending.
            """
            # Do something here
            # ...
            # Internal API call to set the state flag
            self.state = self.pending

        @pending.transition(published, 'can_publish', title="Publish")
        def publish(self, context=None):
            """
            Publish the document.
            """
            # Also do something here
            if not self.document.email_verified:
                raise TransitionException("Email address is not verified.")
            self.state = self.published


    # Apply workflow to document
    >>> doc = MyDocument()
    >>> wf = MyDocumentWorkflow(doc)
    >>> wf.draft()
    True
    >>> wf.pending()
    False
    >>> wf.not_published()
    True
    >>> wf.state
    <WorkflowState "Draft">

    >>> wf.all_states() # All states
    [<WorkflowState "Draft">, <WorkflowState "Pending">, <WorkflowState "Published">,
    <WorkflowState "Withdrawn">, <WorkflowState "Rejected">]

    >>> wf.transitions(context=None) # Available transitions
    [<WorkflowTransition "Submit">]

    >>> wf.submit() # Perform a transition
    >>> wf.state
    <WorkflowState "Pending">
