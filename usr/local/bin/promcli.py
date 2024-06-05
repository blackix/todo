import curses
import sqlite3

DB_FILE = '/var/lib/todo_app/todos.db'

COLOR_MAP = {
    "black": curses.COLOR_BLACK,
    "red": curses.COLOR_RED,
    "green": curses.COLOR_GREEN,
    "yellow": curses.COLOR_YELLOW,
    "blue": curses.COLOR_BLUE,
    "magenta": curses.COLOR_MAGENTA,
    "cyan": curses.COLOR_CYAN,
    "white": curses.COLOR_WHITE,
    "grey": 8  # Define grey color
}

THEMES = {
    "light": {
        "background": curses.COLOR_WHITE,
        "text": curses.COLOR_BLACK,
        "linenumber": curses.COLOR_YELLOW,
        "prompt_bg": curses.COLOR_BLACK,
        "prompt_text": curses.COLOR_YELLOW,
    },
    "dark": {
        "background": curses.COLOR_BLACK,
        "text": curses.COLOR_WHITE,
        "linenumber": curses.COLOR_YELLOW,
        "prompt_bg": COLOR_MAP["grey"],
        "prompt_text": curses.COLOR_WHITE,
    }
}

COMMANDS = [":d ", ":p ", ":x ", ":q ", ":theme "]

def strikethrough(text):
    return ''.join(c + '\u0336' for c in text)

class ToDoApp:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.todos = []
        self.highlighted = set()
        self.priorities = set()
        self.current_theme = "dark"  # Default theme
        self.init_colors()
        self.load_todos()
        self.run()

    def init_colors(self):
        curses.start_color()
        for color_name, color_value in COLOR_MAP.items():
            if color_value > 7:
                curses.init_color(color_value, 500, 500, 500)  # Define grey

        self.apply_theme(self.current_theme)

    def apply_theme(self, theme_name):
        if theme_name in THEMES:
            theme = THEMES[theme_name]
            curses.init_pair(1, theme["prompt_text"], theme["prompt_bg"])
            self.prompt_color = curses.color_pair(1)
            curses.init_pair(2, theme["text"], theme["background"])
            self.text_color = curses.color_pair(2)
            curses.init_pair(3, theme["linenumber"], theme["background"])
            self.linenumber_color = curses.color_pair(3)
            self.background_color_pair = curses.color_pair(2)  # Use the same as text background
            self.current_theme = theme_name

    def load_todos(self):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS todos (
                                id INTEGER PRIMARY KEY,
                                content TEXT,
                                highlighted INTEGER,
                                priority INTEGER)''')
            cursor.execute('SELECT * FROM todos')
            rows = cursor.fetchall()
            for row in rows:
                self.todos.append(row[1])
                if row[2]:
                    self.highlighted.add(len(self.todos) - 1)
                if row[3]:
                    self.priorities.add(len(self.todos) - 1)
            conn.close()
        except Exception as e:
            self.log_error(f"Error loading todos: {e}")

    def save_todos(self):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM todos')
            for i, todo in enumerate(self.todos):
                cursor.execute('INSERT INTO todos (content, highlighted, priority) VALUES (?, ?, ?)',
                               (todo, int(i in self.highlighted), int(i in self.priorities)))
            conn.commit()
            conn.close()
        except Exception as e:
            self.log_error(f"Error saving todos: {e}")

    def fill_background(self):
        try:
            height, width = self.stdscr.getmaxyx()
            for y in range(height):
                self.stdscr.addstr(y, 0, " " * width, self.background_color_pair)
        except Exception as e:
            self.log_error(f"Error filling background: {e}")

    def draw(self, input_str="", suggestions=None, selected_suggestion_index=None):
        try:
            self.stdscr.clear()
            self.fill_background()
            height, width = self.stdscr.getmaxyx()

            # Draw todos
            for i, todo in enumerate(self.todos):
                attr = self.text_color
                display_text = todo
                if i in self.priorities:
                    attr |= curses.A_BOLD
                if i in self.highlighted:
                    display_text = strikethrough(todo)
                    line_number = "✔"
                else:
                    line_number = f"{i + 1}."

                self.stdscr.addstr(i, 4, display_text, attr)
                self.stdscr.addstr(i, 0, line_number, self.linenumber_color)

            # Draw prompt with custom color
            self.stdscr.addstr(height - 1, 0, "> ", self.prompt_color)
            self.stdscr.addstr(height - 1, 2, input_str, self.text_color)

            # Show suggestions if available
            if suggestions:
                for idx, suggestion in enumerate(suggestions):
                    suggestion_attr = self.text_color
                    if idx == selected_suggestion_index:
                        suggestion_attr |= curses.A_REVERSE
                    self.stdscr.addstr(height - 2 - idx, 0, suggestion, suggestion_attr)

            self.stdscr.clrtoeol()  # Clear the rest of the line
            self.stdscr.refresh()
        except Exception as e:
            self.log_error(f"Error drawing screen: {e}")

    def add_item(self, item):
        self.todos.append(item)

    def highlight_item(self, idx):
        if idx in self.highlighted:
            self.highlighted.remove(idx)
        else:
            self.highlighted.add(idx)

    def prioritize_item(self, idx):
        if idx in self.priorities:
            self.priorities.remove(idx)
        else:
            self.priorities.add(idx)

    def delete_items(self, indices):
        indices = sorted(indices, reverse=True)
        for idx in indices:
            if idx < len(self.todos):
                del self.todos[idx]
        self.highlighted = {i if i < idx else i - len(indices) for i in self.highlighted if i not in indices}
        self.priorities = {i if i < idx else i - len(indices) for i in self.priorities if i not in indices}

    def handle_input(self, input_str):
        try:
            if input_str.isdigit():
                idx = int(input_str) - 1
                self.highlight_item(idx)
            elif input_str.startswith(":d "):
                try:
                    idx = int(input_str[3:]) - 1
                    self.highlight_item(idx)
                except ValueError:
                    pass
            elif input_str.startswith(":p "):
                try:
                    idx = int(input_str[3:]) - 1
                    self.prioritize_item(idx)
                except ValueError:
                    pass
            elif input_str.startswith(":x "):
                try:
                    ranges = input_str[3:].split(',')
                    indices = []
                    for range_str in ranges:
                        if '-' in range_str:
                            start, end = map(int, range_str.split('-'))
                            indices.extend(range(start-1, end))
                        else:
                            indices.append(int(range_str) - 1)
                    self.delete_items(indices)
                except ValueError:
                    pass
            elif input_str.startswith(":theme "):
                theme_name = input_str[7:].strip().lower()
                self.apply_theme(theme_name)
            elif input_str.strip() == ":q":
                self.save_todos()
                return False  # Signal to exit the app
            else:
                self.add_item(input_str)
            self.save_todos()  # Save todos after each modification
            return True
        except Exception as e:
            self.log_error(f"Error handling input: {e}")
            return True

    def get_suggestions(self, input_str):
        if input_str.startswith(":"):
            return [cmd for cmd in COMMANDS if cmd.startswith(input_str)]
        return []

    def log_error(self, message):
        with open("error.log", "a") as log_file:
            log_file.write(message + "\n")

    def run(self):
        curses.echo()
        input_str = ""
        suggestions = []
        selected_suggestion_index = None
        running = True
        while running:
            self.draw(input_str, suggestions, selected_suggestion_index)
            key = self.stdscr.getch()

            if key == curses.KEY_BACKSPACE or key == 127:
                input_str = input_str[:-1]
                suggestions = self.get_suggestions(input_str)
                selected_suggestion_index = 0 if suggestions else None
            elif key == 9 and input_str.startswith(":"):  # Tab key
                suggestions = self.get_suggestions(input_str)
                selected_suggestion_index = 0 if suggestions else None
            elif key == curses.KEY_UP and suggestions:
                if selected_suggestion_index is not None:
                    selected_suggestion_index = (selected_suggestion_index - 1) % len(suggestions)
            elif key == curses.KEY_DOWN and suggestions:
                if selected_suggestion_index is not None:
                    selected_suggestion_index = (selected_suggestion_index + 1) % len(suggestions)
            elif key == 10:  # Enter key
                if selected_suggestion_index is not None and suggestions:
                    input_str = suggestions[selected_suggestion_index]
                    suggestions = []
                    selected_suggestion_index = None
                else:
                    running = self.handle_input(input_str)
                    input_str = ""
                    suggestions = []
                    selected_suggestion_index = None
            else:
                input_str += chr(key)
                suggestions = self.get_suggestions(input_str)
                selected_suggestion_index = 0 if suggestions else None
            self.stdscr.clear()

def main(stdscr):
    try:
        app = ToDoApp(stdscr)
    except Exception as e:
        with open("error.log", "a") as log_file:
            log_file.write(f"Critical error: {e}\n")

curses.wrapper(main)

