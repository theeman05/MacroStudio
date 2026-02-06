# Python Macro Engine

![License](https://img.shields.io/badge/license-GPLv3-blue.svg) ![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![Status](https://img.shields.io/badge/status-Active%20Development-green) [![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Donate-yellow.svg)](https://buymeacoffee.com/dbhs)

**Limitless automation, powered by Python.**

The **Python Macro Engine** is a robust automation framework that bridges the gap between simple macro recorders and complex software development. Unlike traditional click-recorders, this engine allows you to script logic in pure Python, giving you access to the full power of the language—from computer vision (OpenCV) to API requests—while managing the lifecycle of your tasks through a user-friendly GUI.

## 🚀 Key Features

### 🐍 Infinite Possibilities
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
* **Automatic Serialization:** The engine knows how to save and load your object from config files. **COMING SOON**

---

Here is the updated **Usage Section** including the new step for **Threaded Tasks**.

I have structured it to clearly distinguish between the "Generator Method" (efficient, main thread) and the "Threaded Method" (good for blocking operations), as they require slightly different sleep commands.

You can paste this entire block into your `README.md`.

## 🛠️ Usage

### 1. Create a Standard Task (Generators)
The most efficient way to write tasks is using Python Generators. This allows the engine to run hundreds of tasks simultaneously on a single thread.

* **Key Rule:** Use `yield from macroSleep(seconds)` instead of `time.sleep()` in standard tasks.

```python
from macro_creator import macroSleep


def my_task():
    # Can print to the python terminal
    print("Task starting...")
    # Engine runs other tasks while this waits
    yield from macroSleep(1)
    print("Task resumed!")


class BasicMacro:
    def __init__(self, macro_creator):
        self.engine = macro_creator
        # Add the task to the creator
        macro_creator.addRunTask(my_task)

```

### 2. Controlling Tasks

When you add a task, the engine returns a **Controller**. You can use this object to pause, resume, or stop other tasks dynamically.

```python
    def __init__(self, macro_creator):
        self.engine = macro_creator
        # Save the controller to a variable
        self.worker_ctrl = macro_creator.addRunTask(self.my_task)
        # Add a variable so the user can choose to sleep "my_task" or not and set the default value to "True"
        macro_creator.addVariable("Sleep My Task", bool, True, "Sleeps My Task On Execute")
        macro_creator.addRunTask(self.manager_task)

    def manager_task(self, controller):
        # Log directly to the ui
        controller.log("I am going to sleep")
        # Get a user defined variable from the engine
        if self.engine.getVar("Sleep My Task"):
            self.worker_ctrl.pause() # Worker stops immediately
            yield from macroSleep(2)
            self.worker_ctrl.resume() # Worker continues

```

### 3. Threaded Tasks (Blocking Code)

Sometimes you need to run blocking code (like heavy calculations or network requests) that doesn't support generators. You can run these in a separate thread while keeping them synchronized with the engine's Pause/Stop system.

* **Key Rule:** Pass the `TaskController` to your thread and use `controller.sleep(seconds)`. This ensures the thread pauses correctly if the user hits the global Pause button.

```python
import threading
from macro_creator import macroSleep, macroRunTaskInThread


# 1. Define the function to run in the thread
def heavy_lifting(controller):
    print("Running in a separate thread!")
    # SAFE SLEEP: Checks if the user paused the engine while sleeping
    controller.sleep(5)
    print("Thread finished work.")

def launcher(controller):
    # Create and start thread task with the argument being the task controller
    controller.log("Starting background work...")
    # Yield while the thread task is running
    yield from macroRunTaskInThread(heavy_lifting, controller=controller)

class ThreadMacro:
    def __init__(self, macro_creator):
        # 2. Add a task that spawns the thread
        # We pass 'self.launcher' so we can get its controller
        self.engine = macro_creator
        self.controller = macro_creator.addRunTask(launcher)

```

### 4. Running the Engine

Launch the GUI. Your tasks and variables will automatically appear.

```python
from macro_creator import MacroCreator
from Examples.basic_macro import BasicMacro

if __name__ == "__main__":
    creator = MacroCreator()

    # Add steps and tasks from BasicMacro
    BasicMacro(creator)

    creator.launch()

```

* **Edit Configs:** Click any task to modify its variables.
* **Start/Pause/Stop:** Use the global controls or manage tasks individually.
* **Visual Debugging:** Hover over region variables to see them highlighted on screen.

### ⚙️ How it Works Under the Hood

* **Generator Tasks:** Use **Cooperative Multitasking**. The engine cycles through tasks, running them until they `yield`. This makes the bot extremely lightweight and CPU efficient.
* **Threaded Tasks:** Run in parallel. By using `controller.sleep()`, you bridge the gap, allowing the main engine to safely pause or stop these threads even though they are running outside the main loop.

Here is a "Feature Highlight" block for your documentation. You can place this under your **Key Features** or **Developer API** section.

It highlights the system's ability to seamlessly bridge raw Python code with a user-friendly GUI.

---

### ⚠️ Critical Rule: Handling Hard Pauses When Sleeping Tasks

**Rule:** When a task yields time back to the engine, you **must** wrap your sleep calls in a `try/except` block to handle `MacroHardPauseException`.

**Reason:** The Engine uses `MacroHardPauseException` to interrupt execution immediately when a controller or the engine is hard paused.

* **If you catch it:** Your code pauses, waits to resume, and then continues like normal.
* **If you DO NOT catch it:** The exception bubbles up, **returning immediately**. Your task will mistakenly treat a "Pause" as a "Stop/Cancel" and exit the loop prematurely.

#### ❌ Incorrect Implementation (Broken on Hard Pause)

In this example, if the task is Hard Paused, the loop crashes, and the code after will not run.

```python
counter = 0
while counter < 10:
    # DANGER: If the task is Hard Paused, this line raises MacroHardPauseException.
    # Since it isn't caught, it exits the 'while' loop immediately!
    yield from macroSleep(1)
    counter += 1
    
print("Task finished!") # <--- This will not run on resuming (Wrong!)

```

#### ✅ Correct Implementation (Resumable)

You must catch the exception and delegate control to `macroWaitForResume()`.

```python
counter = 0
while counter < 10:
    try:
        # Try to sleep normally
        yield from macroSleep(1) 
        
    except MacroHardPauseException:
        # CAUGHT: User paused. Wait here until they click Resume.
        # When this returns, execution loops back naturally.
        yield from macroWaitForResume()
    counter += 1

print("Thread finished!") # <--- Only runs when thread is ACTUALLY done.

```

### ⚠️ Critical Rule: Handling Stops (`MacroAbortException`)

**Rule:** Calls to `controller.sleep`, `waitForResume`, or any blocking method will raise `MacroAbortException` if the task is stopped while waiting. You **must not catch and ignore** this exception. Instead, use a `try/finally` block to ensure resources (files, connections, etc.) are closed properly when the task is terminated.

**Reason:** The engine uses this exception to immediately halt execution. Swallowing this exception (catching it without re-raising or returning) will cause your thread to keep running as a "phantom process" even after the user has clicked Stop.

**Note:** `MacroAbortException` abort exception does not apply to non-threaded tasks using `macroSleep()` or `macroWaitForResume()`. However, they should still follow this rule to ensure resources (files, connections, etc.) are closed properly when the task is terminated.

#### ❌ Incorrect Implementation (The Phantom Thread)

In this example, the user catches `Exception` (which includes `MacroAbortException`), logs it, and **continues the loop**. The thread refuses to die.

```python
# Bad Pattern: Swallowing the Stop signal
f = open("log.txt", "w")

while True:
    try:
        # If user clicks STOP, this raises MacroAbortException
        controller.sleep(1)
        do_work()
        
    except Exception as e:
        # DANGER: This catches MacroAbortException too!
        # The code logs the error but the loop keeps spinning.
        print(f"Error occurred: {e}")

# This line is never reached if the loop doesn't break
f.close() 

```

#### ✅ Correct Implementation (The `finally` Pattern)

Use `finally` to guarantee cleanup. You do not need to explicitly catch `MacroAbortException` because you *want* it to propagate up and stop the thread.

```python
# Good Pattern: Resource safety
f = open("log.txt", "w")

try:
    while True:
        # If user clicks STOP, exception triggers cleanup immediately
        controller.sleep(1)
        do_work()
        
finally:
    # This block GUARANTEES execution:
    # 1. If the loop finishes normally
    # 2. If a crash happens
    # 3. If the user clicks STOP (MacroAbortException)
    print("Closing file...")
    f.close()

```

---

### 🧬 How to Add Custom Types

Registering a new type is as simple as adding a decorator. You define how to **Read (Parse)** and **Write (Format)** the value, and the engine handles the rest.

```python
from macro_creator import registerHandler

@registerHandler
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

### 💾 Variable Serialization & State Persistence

Currently, task variables live entirely in memory; if you close the app, the data is lost. I will be building a powerful serialization layer that allows the engine to snapshot and save the exact state of your variables to the disk.

**Planned Capabilities:**

* **Variable Reloading:** If the application (or your computer) crashes mid-task, the engine will be able to reload the task with all local variables restored to their last known state. `counter=500` remains `500`, rather than resetting to `0`.

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

If you find this creator helpful and want to support its development, consider buying me a coffee! It helps keep the updates coming.

<a href="https://buymeacoffee.com/dbhs" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

## 📄 License

Distributed under the **GNU GPLv3 License**. See `LICENSE` for more information.
*This means that if you modify and distribute this engine or build a product on top of it, you must keep it open-source.*