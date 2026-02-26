class ApprovalEvent:
    def __init__(self, value):
        self.value = value        # The data being proposed (e.g., "New Name")
        self._accepted = False
        self._reason = ""
        self.return_data = None   # NEW: To pass back the newly created database object

    def accept(self, return_data=None):
        """Mark the change as valid, optionally passing back the updated data object."""
        self._accepted = True
        self._reason = ""
        self.return_data = return_data

    def ignore(self, reason: str = "Action declined"):
        """Mark the change as invalid with a specific error message."""
        self._accepted = False
        self._reason = reason

    @property
    def isAccepted(self): return self._accepted

    @property
    def reason(self): return self._reason