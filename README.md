# Python Macro Studio

![License](https://img.shields.io/badge/license-GPLv3-blue.svg) ![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![Status](https://img.shields.io/badge/status-Active%20Development-green) [![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Donate-yellow.svg)](https://buymeacoffee.com/dbhs)

**Limitless automation, powered by Python.**

The **Python Macro Studio** is a robust automation framework that bridges the gap between simple macro recorders and complex software development. Unlike traditional click-recorders, this engine allows you to script logic in pure Python, giving you access to the full power of the language, from computer vision (OpenCV) to API requests while managing the lifecycle of your tasks through a user-friendly GUI.

## 🚀 Key Features

### ♾️ Infinite Possibilities
If you can code it in Python, you can automate it. Import any library, use complex logic, and interact with the OS at a deep level. You are not limited to "click here, wait 5 seconds."

### 🎛️ Granular Task Control
The core of the engine is its **Task Manager**. Unlike standard scripts that run from top to bottom:
* **Individual Control:** Pause, Stop, or Restart specific tasks without stopping the whole engine.
* **Hot-Swappable:** Update variables in real-time while the macro is running.
* **Resilient:** If one task crashes or is stopped, the rest of the engine keeps running.

### 🧩 Variable Management
Predefine variables (Integers, Booleans, Regions, Points, etc.) that are exposed in the GUI. Users can tweak settings (like `click_point` or `scan_region`) safely via the interface without ever touching the code.

### ⚡ Smart Config
Variables are type-safe and validated instantly. As of right now, the engine supports complex types like `QRect` (Regions) and `QPoint` (Coordinates) with visual overlays, ensuring users don't have to guess pixel coordinates (but they still can if they want to)!

### 🧬 Extensible Type System

The Engine features a robust **Global Type Registry** that bridges the gap between Python objects and the User Interface. You don't need to manually build widgets for your settings; simply defining a type handler automatically grants you:

* **Smart UI Handling:** Users see friendly names (e.g., "Screen Region") instead of raw class names (e.g., `PySide6.QtCore.QRect`).
* **Input Validation:** The UI provides immediate visual feedback (red borders/tooltips) if user input doesn't match your parser's rules.
* **Automatic Serialization:** The engine knows how to save and load your object from config files.

---

## 🛠️ Usage

### 1. Create a Standard Task (Generators)
The most efficient way to write tasks is using Python Generators. This allows the engine to run hundreds of tasks simultaneously on a single thread.

* **Key Rule:** Use `yield from taskSleep(seconds)` instead of `time.sleep()` in standard tasks.

```python
from macro_studio import Controller, taskSleep


def my_task():
    # Can print to the python terminal
    print("Task starting...")
    # Engine runs other tasks while this waits
    yield from taskSleep(1)
    print("Task resumed!")


class BasicMacro:
    def __init__(self, studio):
        # Add the task to the studio
        studio.addRunTask(my_task)

```

### 2. Controlling Tasks

When you add a task, the engine returns a **Task Controller**. You can use this object to pause, resume, or stop other tasks dynamically.

```python
    def __init__(self, studio):
    self.studio = studio
    # Save the controller to a variable
    self.worker_ctrl = studio.addRunTask(self.my_task)
    # Add a variable so the user can choose to sleep "my_task" or not and set the default value to "True"
    studio.addVar("Sleep My Task", bool, True, "Sleeps My Task On Execute")
    studio.addRunTask(self.manager_task)


def manager_task(self, controller: Controller):
    # Log directly to the ui
    controller.log("I am going to sleep")
    # Get a user defined variable from the engine
    if controller.getVar("Sleep My Task"):
        self.worker_ctrl.pause()  # Worker stops immediately
        yield from taskSleep(2)
        self.worker_ctrl.resume()  # Worker continues

```

### 3. Threaded Tasks (Blocking Code)

Sometimes you need to run blocking code (like heavy calculations or network requests) that doesn't support generators. You can run these in a separate thread while keeping them synchronized with the engine's Pause/Stop system.

* **Key Rule:** Pass the `TaskController` to your thread and use `controller.sleep(seconds)`. This ensures the thread pauses correctly if the task is paused.

```python
import threading
from macro_studio import Controller, taskSleep, taskAwaitThread


# 1. Define the function to run in the thread
def heavy_lifting(controller: Controller):
    print("Running in a separate thread!")
    # SAFE SLEEP: Checks if the user paused the engine while sleeping
    controller.sleep(5)
    print("Thread finished work.")


def launcher(controller: Controller):
    # Create and start thread task with the argument being the task controller
    controller.log("Starting background work...")
    # Yield while the thread task is running
    yield from taskAwaitThread(heavy_lifting, controller=controller)


class ThreadMacro:
    def __init__(self, studio):
        # 2. Add a task that spawns the thread
        # We pass 'self.launcher' so we can get its controller
        self.studio = studio
        self.controller = studio.addRunTask(launcher)

```

### 4. Running the Engine

Launch the GUI. Your tasks and variables will automatically appear.

```python
from macro_studio import MacroStudio
from Examples.basic_macro import BasicMacro

if __name__ == "__main__":
    studio = MacroStudio(macro_name="Basic Macro Example")

    # Add steps and tasks from BasicMacro
    BasicMacro(studio)

    studio.launch()

```

* **Edit Configs:** Click any task to modify its variables.
* **Start/Pause/Stop:** Use the global controls or manage tasks individually.
* **Visual Debugging:** Hover over region variables to see them highlighted on screen.

### ⚙️ How it Works Under the Hood

* **Generator Tasks:** Use **Cooperative Multitasking**. The engine cycles through tasks, running them until they `yield`. This makes the bot extremely lightweight and CPU efficient.
* **Threaded Tasks:** Run in parallel. By using `controller.sleep()`, you bridge the gap, allowing the main engine to safely pause or stop these threads even though they are running outside the main loop.

---

### 🛡️ Handling Control Flow: Pauses & Stops

The Engine uses exceptions to control your tasks. You must handle these correctly to ensure your macro pauses and stops safely when the user expects it to.

---

#### ⚠️ 1. Handling Task Interruptions

**The Exception:** `TaskInterruptedException`
**The Scenario:** When the user interrupts a task, the engine immediately interrupts the current action (like a long sleep) to release keys and clean up.

* **If you DO NOT catch it:** The exception bubbles up and exits your task. Your loop will terminate prematurely.
* **If you DO catch it:** You can save the state, yield a wait command, and then resume the loop when the user is ready.

**✅ Correct Pattern: The Resumable Loop**
To make a robust loop that survives an interruption, wrap your logic in a `try/except` block and delegate control to `taskWaitForResume`.

```python
from macro_studio import TaskInterruptedException, taskSleep, taskWaitForResume


def task_count_to_ten():
    counter = 0
    while counter < 10:
        try:
            # 1. Try to sleep normally
            yield from taskSleep(1)

        except TaskInterruptedException:
            # 2. INTERRUPTED! The task was interrupted while paused.
            # We yield to the pause handler so the engine waits here.
            yield from taskWaitForResume()

            # 3. When we return here, the loop continues naturally.

        counter += 1

    print("Task finished successfully!")

```

**❌ Incorrect Pattern: The Fragile Loop**
In this example, an interruption crashes the loop because the exception is not handled.

```python
def task_fragile_count():
    counter = 0
    while counter < 10:
        # DANGER: If interrupted, this line raises TaskInterruptedException.
        # Since it isn't caught, the function aborts immediately!
        yield from task_sleep(1) 
        counter += 1

    # This line is NEVER reached if the task is interrupted.
    print("Task finished!") 

```

---

#### 🛑 2. Handling Stops (Aborting)

**The Exception:** `TaskAbortException`
**The Scenario:** When the user clicks **Stop**, the engine raises this exception in any blocking method (`controller.sleep`, `waitForResume`) to halt execution immediately.

**The Rule:** You **must never catch and ignore** this exception.

* **Do:** Use `try/finally` blocks to ensure resources (files, database connections) are closed.
* **Do Not:** Use a bare `except:` or `except TaskAbortException:` that swallows the stop signal.

**✅ Correct Pattern: The `finally` Cleanup**
Use `finally` to guarantee cleanup. You do not need to explicitly catch `TaskAbortException` because you *want* it to propagate up and stop the thread.

```python
from macro_studio import Controller
def task_write_log(controller: Controller):
    # Open a resource that MUST be closed later
    f = open("log.txt", "w")
    
    try:
        while True:
            # If user clicks STOP, 'controller.sleep' raises TaskAbortException
            controller.sleep(1)
            f.write("Working...\n")
            
    finally:
        # This block ALWAYS runs, even if the task is Stopped/Aborted.
        print("Cleanup: Closing file safely.")
        f.close()

```

**❌ Incorrect Pattern: The "Phantom Thread"**
Swallowing the exception causes the thread to stay alive as a "zombie" process, continuing to run even after the user thinks they stopped it.

```python
from macro_studio import Controller, TaskAbortException


def task_zombie_log(controller: Controller):
    while True:
        try:
            controller.sleep(1)
            do_work()

        except TaskAbortException as e:
            # ⛔ DANGER: You caught the Stop signal and only printed it!
            # The loop will just spin around and run again.
            print(f"Stop ignored: {e}")

```

---

### 🧬 How to Add Custom Types

Registering a new type is as simple as adding a decorator. You define how to **Read (Parse)** and **Write (Format)** the value, and the engine handles the rest.

```python
from macro_studio import register_handler


@register_handler
class HeroData:
    """
    A custom class to store hero configuration.
    The 'display_name' attribute determines what the user sees in the UI tooltip.
    """
    display_name = "Hero Configuration"

    def __init__(self, name, level):
        self.name = name
        self.level = level

    @staticmethod
    def toString(obj):
        # Convert object to string for the UI/Config file
        return f"{obj.name}:{obj.level}"

    @staticmethod
    def fromString(text):
        # Convert string back to object
        try:
            name, level = text.split(':')
            return HeroData(name, int(level))
        except ValueError:
            raise ValueError("Format must be 'Name:Level'")

```

#### Supported Out-of-the-Box

The engine comes pre-configured with handlers for standard and GUI types:

* **Python Primitives:** `int`, `float`, `bool`, `str`, `list`, `tuple`
* **Qt Geometry:** `QRect` (Screen Region), `QPoint` (Coordinate)
* **Custom Extensions:** Add any class you want using the `@registerHandler` decorator or the type handler's `register` method.

---

## 🔮 Roadmap & Coming Soon

I am actively working to make this the ultimate automation platform. Here is what is coming next:

### 🎥 Visual Task Recorder (No-Code)

I will be lowering the barrier to entry!

* **Record:** Create new tasks by simply recording your mouse and keyboard actions—no coding required.
* **Edit:** Fine-tune your recorded actions directly in the Engine's GUI (change delays, adjust coordinates) without opening a text editor.

---

## 🤝 Contributing

Contributions are welcome! Whether you are fixing bugs, adding new features, or creating example tasks, I would love to see your work :)

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## ☕ Support the Project

If you find this studio helpful and want to support its development, consider buying me a coffee! It helps keep the updates coming.

<a href="https://buymeacoffee.com/dbhs" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

## 📄 License

Distributed under the **GNU GPLv3 License**. See `LICENSE` for more information.
*This means that if you modify and distribute this engine or build a product on top of it, you must keep it open-source.*