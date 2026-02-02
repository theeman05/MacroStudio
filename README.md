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
Predefine variables (Integers, Booleans, Regions, Points) that are exposed in the GUI. Users can tweak settings (like `click_point` or `scan_region`) safely via the interface without ever touching the code.

### ⚡ Smart Config
Variables are type-safe and validated instantly. As of right now, the engine supports complex types like `QRect` (Regions) and `QPoint` (Coordinates) with visual overlays, ensuring users don't have to guess pixel coordinates (but they still can if they want to)!

---

Here is the updated **Usage Section** including the new step for **Threaded Tasks**.

I have structured it to clearly distinguish between the "Generator Method" (efficient, main thread) and the "Threaded Method" (good for blocking operations), as they require slightly different sleep commands.

You can paste this entire block into your `README.md`.

## 🛠️ Usage

### 1. Create a Standard Task (Generators)
The most efficient way to write tasks is using Python Generators. This allows the engine to run hundreds of tasks simultaneously on a single thread.

* **Key Rule:** Use `yield from macroSleep(seconds)` instead of `time.sleep()` in standard tasks.

```python
from utils import macroSleep


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

    def manager_task(self):
        # Log directly to the ui
        self.engine.ui.log("I am going to sleep")
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
from utils import macroSleep

# 1. Define the function to run in the thread
def heavy_lifting(controller):
    print("Running in a separate thread!")
    
    # SAFE SLEEP: Checks if the user paused the engine while sleeping
    controller.sleep(5) 
    
    print("Thread finished work.")

class ThreadMacro:
    def __init__(self, macro_creator):
        # 2. Add a task that spawns the thread
        # We pass 'self.launcher' so we can get its controller
        self.engine = macro_creator
        self.controller = macro_creator.addRunTask(self.launcher)

    def launcher(self):
        # 3. Start thread and pass the controller to it
        t = threading.Thread(target=heavy_lifting, args=(self.controller,), daemon=True)
        t.start()
        
        # Let the engine know we have a task running still while the thread is still running
        while self.engine.isRunningMacros() and t.is_alive():
            yield from macroSleep(1)

```

### 4. Running the Engine

Launch the GUI. Your tasks and variables will automatically appear.

```python
from engine import MacroCreator
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


---

## 🔮 Roadmap & Coming Soon

I am actively working to make this the ultimate automation platform. Here is what is coming next:

### 🛑 "Hard Pause" & Cleanup

Currently, pausing a task suspends tasks on their next sleep cycle. I will be introducing a **Hard Pause** system to default to.

* **What it means:** When you pause, the engine will respect `finally` blocks in your Python code.
* **Why it matters:** This ensures connections are closed, files are saved, and resources are released cleanly, even when the user hits pause.

### 🎥 Visual Task Recorder (No-Code)

I will be lowering the barrier to entry!

* **Record:** Create new tasks by simply recording your mouse and keyboard actions—no coding required.
* **Edit:** Fine-tune your recorded actions directly in the Engine's GUI (change delays, adjust coordinates) without opening a text editor.

---

## 🤝 Contributing

Contributions are welcome! Whether you are fixing bugs, adding new features, or creating example tasks, I would love to see your work :).

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