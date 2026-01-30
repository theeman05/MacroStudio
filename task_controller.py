

class TaskController:
    def __init__(self, task_func, task_id: int):
        self.id = task_id
        self.func = task_func

        self.generation = 0
        self._paused = False

    def pause(self):
        """Prevents the task from running its next step. Execution continues until task finishes."""
        self._paused = True

    def resume(self):
        """Allows the task to continue from where it left off."""
        self._paused = False

    def stop(self):
        """Stops a task, entirely, allowing execution to finish"""
        self._paused = False
        self.generation = -1

    def reset(self):
        """Kills the current instance of the task and starts a fresh one immediately."""
        self.generation += 1
        self._paused = False