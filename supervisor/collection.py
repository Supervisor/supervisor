class Collection:
    """A logical grouping of processes from potentially different groups.
    Collections do not own process lifecycle — they are purely
    organizational and delegate start/stop to the owning groups."""

    def __init__(self, config, members):
        self.config = config          # CollectionConfig
        self.members = members        # list of (ProcessGroup, Subprocess) tuples

    def get_processes(self):
        """Return list of (group, process) tuples."""
        return list(self.members)
