import curses
import sqlite3
import os
import requests
import random
import string
import datetime

DB_HOST = 'http://127.0.0.1:5000'
UPLOAD_ENDPOINT = '/upload'
UPLOAD_FOLDER = 'uploads'

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
        "prompt_bg": curses.COLOR_BLACK,
        "prompt_text": curses.COLOR_WHITE,
    }
}

COMMANDS = {
    ":d ": "done, completato",
    ":p ": "priorità",
    ":x ": "cancella rigo. 1,3,5 oppure 2-6",
    ":q ": "quit, chiudi app",
    ":theme ": "tema può essere 'dark' o 'light'",
    ":b ": "evidenzia in grassetto una nota",
    ":i ": "evidenzia in corsivo una nota",
    ":s ": "salva il database sul server HTTP",
    ":check ": "controlla se il database è salvato sul server HTTP"
}

def strikethrough(text):
    return ''.join(c + '\u0336' for c in text)

def generate_code(length=4):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

class ToDoApp:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.todos = []
        self.subtodos = {}
        self.highlighted = set()
        self.priorities = set()
        self.bold_notes = set()
        self.italic_notes = set()
        self.current_theme = "dark"
        self.db_code = None
        self.db_file = None
        self.last_saved = "Not yet saved"
        self.http_status = "Disconnected"
        self.init_colors()
        self.initialize_database()
        self.load_todos()
        self.run()

    def init_colors(self):
        curses.start_color()
        for color_name, color_value in COLOR_MAP.items():
            if color_value > 7:
                curses.init_color(color_value, 500, 500, 500)  # Define grey

        self.apply_theme(self.current_theme)
        curses.init_pair(5, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Green line color
        self.divider_color = curses.color_pair(5)
        curses.init_pair(6, curses.COLOR_RED, curses.COLOR_BLACK)  # Red for strikethrough icon
        self.strikethrough_icon_color = curses.color_pair(6)
        curses.init_pair(7, curses.COLOR_MAGENTA, curses.COLOR_BLACK)  # Pink for bold
        self.bold_color = curses.color_pair(7)
        curses.init_pair(8, curses.COLOR_BLUE, curses.COLOR_BLACK)  # Blue for italic
        self.italic_color = curses.color_pair(8)

    def apply_theme(self, theme_name):
        if theme_name in THEMES:
            theme = THEMES[theme_name]
            curses.init_pair(1, theme["prompt_text"], theme["prompt_bg"])
            self.prompt_color = curses.color_pair(1)
            curses.init_pair(2, theme["text"], theme["background"])
            self.text_color = curses.color_pair(2)
            curses.init_pair(3, theme["linenumber"], theme["background"])
            self.linenumber_color = curses.color_pair(3)
            curses.init_pair(4, curses.COLOR_RED, theme["background"])  # Prompt symbol color
            self.prompt_symbol_color = curses.color_pair(4)
            self.background_color_pair = curses.color_pair(2)  # Use the same as text background
            self.current_theme = theme_name

    def initialize_database(self):
        self.db_code = self.prompt_for_code()
        if self.db_code:
            self.db_file = f"{self.db_code}.db"
            if not self.download_db_if_exists():
                self.db_code = generate_code()
                with open("db_code.txt", "w") as f:
                    f.write(self.db_code)
                self.db_file = f"{self.db_code}.db"
                self.create_db_if_not_exists()

    def prompt_for_code(self):
        return self.file_explorer()

    def file_explorer(self):
        files = self.list_db_files()
        if not files:
            return None
        
        selected_index = 0
        while True:
            self.stdscr.clear()
            self.stdscr.addstr(0, 0, "Select a database file:")
            for idx, file in enumerate(files):
                if idx == selected_index:
                    self.stdscr.addstr(idx + 1, 0, file, curses.A_REVERSE)
                else:
                    self.stdscr.addstr(idx + 1, 0, file)
            self.stdscr.refresh()

            key = self.stdscr.getch()
            if key == curses.KEY_UP and selected_index > 0:
                selected_index -= 1
            elif key == curses.KEY_DOWN and selected_index < len(files) - 1:
                selected_index += 1
            elif key == curses.KEY_ENTER or key == 10:
                return files[selected_index].replace('.db', '')

    def list_db_files(self):
        try:
            response = requests.get(f"{DB_HOST}{UPLOAD_ENDPOINT}")
            if response.status_code == 200:
                files = response.json()
                return [file for file in files if file.endswith('.db')]
            else:
                self.log_error(f"Failed to list files on HTTP server: {response.status_code}")
                return []
        except Exception as e:
            self.log_error(f"Error listing files on HTTP server: {e}")
            return []

    def create_db_if_not_exists(self):
        try:
            if not os.path.exists(self.db_file):
                conn = sqlite3.connect(self.db_file)
                cursor = conn.cursor()
                cursor.execute('''CREATE TABLE IF NOT EXISTS todos (
                                    id INTEGER PRIMARY KEY,
                                    content TEXT,
                                    highlighted INTEGER,
                                    priority INTEGER)''')
                cursor.execute('''CREATE TABLE IF NOT EXISTS subtodos (
                                    id INTEGER PRIMARY KEY,
                                    parent_id INTEGER,
                                    content TEXT,
                                    highlighted INTEGER,
                                    priority INTEGER,
                                    FOREIGN KEY(parent_id) REFERENCES todos(id))''')
                conn.commit()
                conn.close()
                self.log_error("Database created successfully.")
            else:
                self.log_error("Database already exists.")
        except Exception as e:
            self.log_error(f"Error creating database: {e}")

    def download_db_if_exists(self):
        try:
            response = requests.get(f"{DB_HOST}{UPLOAD_ENDPOINT}/{self.db_file}")
            if response.status_code == 200:
                with open(self.db_file, 'wb') as f:
                    f.write(response.content)
                self.log_error("Database downloaded successfully.")
                return True
            else:
                self.log_error("Database not found on HTTP server.")
                return False
        except Exception as e:
            self.log_error(f"Error downloading database: {e}")
            return False

    def load_todos(self):
        try:
            if not os.path.exists(self.db_file):
                self.log_error("No local database file found.")
                return
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM todos')
            rows = cursor.fetchall()
            for row in rows:
                self.todos.append((row[0], row[1]))  # Include ID with the content
                if row[2]:
                    self.highlighted.add(f"{row[0]}")
                if row[3]:
                    self.priorities.add(f"{row[0]}")
            
            cursor.execute('SELECT * FROM subtodos')
            rows = cursor.fetchall()
            for row in rows:
                if row[1] not in self.subtodos:
                    self.subtodos[row[1]] = []
                self.subtodos[row[1]].append((row[0], row[2]))  # Include ID with the content
                if row[3]:
                    self.highlighted.add(f"{row[1]}_{len(self.subtodos[row[1]]) - 1}")
                if row[4]:
                    self.priorities.add(f"{row[1]}_{len(self.subtodos[row[1]]) - 1}")
            
            conn.close()
            self.log_error("Todos and subtodos loaded successfully.")
        except Exception as e:
            self.log_error(f"Error loading todos: {e}")

    def save_todos(self):
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM todos')
            cursor.execute('DELETE FROM subtodos')
            for i, (todo_id, todo) in enumerate(self.todos):
                cursor.execute('INSERT INTO todos (id, content, highlighted, priority) VALUES (?, ?, ?, ?)',
                               (todo_id, todo, int(f"{todo_id}" in self.highlighted), int(f"{todo_id}" in self.priorities)))
                if todo_id in self.subtodos:
                    for j, (subtodo_id, subtodo) in enumerate(self.subtodos[todo_id]):
                        cursor.execute('INSERT INTO subtodos (id, parent_id, content, highlighted, priority) VALUES (?, ?, ?, ?, ?)',
                                       (subtodo_id, todo_id, subtodo, int(f"{todo_id}_{j}" in self.highlighted), int(f"{todo_id}_{j}" in self.priorities)))
            conn.commit()
            conn.close()
            self.last_saved = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.log_error("Todos and subtodos saved successfully.")
        except Exception as e:
            self.log_error(f"Error saving todos: {e}")

    def save_to_http(self):
        try:
            with open(self.db_file, 'rb') as db_file:
                files = {'file': db_file}
                response = requests.post(f"{DB_HOST}{UPLOAD_ENDPOINT}", files=files)
                if response.status_code == 200:
                    self.last_saved = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.log_error("Database saved to HTTP server successfully.")
                else:
                    self.log_error(f"Failed to save database to HTTP server: {response.status_code}")
        except Exception as e:
            self.log_error(f"Error saving database to HTTP server: {e}")

    def check_db_on_http(self):
        try:
            response = requests.head(f"{DB_HOST}{UPLOAD_ENDPOINT}/{self.db_file}")
            if response.status_code == 200:
                self.log_error("Database is present on HTTP server.")
                return True
            else:
                self.log_error("Database is not present on HTTP server.")
                return False
        except Exception as e:
            self.log_error(f"Error checking database on HTTP server: {e}")
            return False

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
            row_idx = 0
            for i in range(height - 5):  # To keep space for the prompt and status lines
                if row_idx < len(self.todos):
                    todo_id, todo = self.todos[row_idx]
                    attr = self.text_color
                    display_text = todo
                    if f"{todo_id}" in self.priorities:
                        attr |= curses.A_BOLD
                    if f"{todo_id}" in self.bold_notes:
                        attr |= curses.A_BOLD | self.bold_color
                    if f"{todo_id}" in self.italic_notes:
                        attr = self.italic_color
                    if f"{todo_id}" in self.highlighted:
                        display_text = strikethrough(todo)
                        self.stdscr.addstr(row_idx, 0, "✔", self.strikethrough_icon_color)
                    else:
                        self.stdscr.addstr(row_idx, 0, f"{i + 1}.", self.linenumber_color)

                    self.stdscr.addstr(row_idx, 4, display_text, attr)
                    row_idx += 1

                    # Draw subtodos if any
                    if todo_id in self.subtodos:
                        for j, (subtodo_id, subtodo) in enumerate(self.subtodos[todo_id]):
                            attr = self.text_color
                            display_text = subtodo
                            subtask_key = f"{todo_id}_{j}"
                            if subtask_key in self.priorities:
                                attr |= curses.A_BOLD
                            if subtask_key in self.bold_notes:
                                attr |= curses.A_BOLD | self.bold_color
                            if subtask_key in self.italic_notes:
                                attr = self.italic_color
                            if subtask_key in self.highlighted:
                                display_text = strikethrough(subtodo)
                                self.stdscr.addstr(row_idx, 4, "✔", self.strikethrough_icon_color)
                            else:
                                self.stdscr.addstr(row_idx, 4, chr(97 + j) + ".", self.linenumber_color)

                            self.stdscr.addstr(row_idx, 8, display_text, attr)
                            row_idx += 1
                else:
                    self.stdscr.addstr(row_idx, 0, "♠", self.linenumber_color)
                    row_idx += 1

            # Draw divider line
            self.stdscr.addstr(height - 4, 0, "-" * width, self.divider_color)

            # Draw prompt with custom color
            self.stdscr.addstr(height - 3, 0, "♥ ", self.prompt_symbol_color)
            self.stdscr.addstr(height - 3, 2, input_str, self.text_color)

            # Draw status line
            status_line = f"DB Code: {self.db_code} | HTTP: {self.http_status} | Last Save: {self.last_saved}"
            self.stdscr.addstr(height - 1, 0, status_line, self.text_color)
            
            # Show suggestions if available
            if suggestions:
                for idx, (cmd, desc) in enumerate(suggestions):
                    suggestion_attr = self.text_color
                    if idx == selected_suggestion_index:
                        suggestion_attr |= curses.A_REVERSE
                    self.stdscr.addstr(height - 5 - idx, 0, f"{cmd} - {desc}", suggestion_attr)

            self.stdscr.clrtoeol()  # Clear the rest of the line
            self.stdscr.refresh()
        except Exception as e:
            self.log_error(f"Error drawing screen: {e}")

    def add_item(self, item):
        new_id = (self.todos[-1][0] + 1) if self.todos else 1
        self.todos.append((new_id, item))  # Add new todo with new ID

    def add_subitem(self, parent_id, item):
        if parent_id not in self.subtodos:
            self.subtodos[parent_id] = []
        new_id = (self.subtodos[parent_id][-1][0] + 1) if self.subtodos[parent_id] else 1
        self.subtodos[parent_id].append((new_id, item))  # Add new subtodo with new ID

    def highlight_item(self, idx):
        todo_id, _ = self.todos[idx]
        if f"{todo_id}" in self.highlighted:
            self.highlighted.remove(f"{todo_id}")
        else:
            self.highlighted.add(f"{todo_id}")

    def highlight_subitem(self, parent_id, sub_idx):
        subtask_key = f"{parent_id}_{sub_idx}"
        if subtask_key in self.highlighted:
            self.highlighted.remove(subtask_key)
        else:
            self.highlighted.add(subtask_key)

    def prioritize_item(self, idx):
        todo_id, _ = self.todos[idx]
        if f"{todo_id}" in self.priorities:
            self.priorities.remove(f"{todo_id}")
        else:
            self.priorities.add(f"{todo_id}")

    def prioritize_subitem(self, parent_id, sub_idx):
        subtask_key = f"{parent_id}_{sub_idx}"
        if subtask_key in self.priorities:
            self.priorities.remove(subtask_key)
        else:
            self.priorities.add(subtask_key)

    def bold_item(self, idx):
        todo_id, _ = self.todos[idx]
        if f"{todo_id}" in self.bold_notes:
            self.bold_notes.remove(f"{todo_id}")
        else:
            self.bold_notes.add(f"{todo_id}")

    def bold_subitem(self, parent_id, sub_idx):
        subtask_key = f"{parent_id}_{sub_idx}"
        if subtask_key in self.bold_notes:
            self.bold_notes.remove(subtask_key)
        else:
            self.bold_notes.add(subtask_key)

    def italic_item(self, idx):
        todo_id, _ = self.todos[idx]
        if f"{todo_id}" in self.italic_notes:
            self.italic_notes.remove(f"{todo_id}")
        else:
            self.italic_notes.add(f"{todo_id}")

    def italic_subitem(self, parent_id, sub_idx):
        subtask_key = f"{parent_id}_{sub_idx}"
        if subtask_key in self.italic_notes:
            self.italic_notes.remove(subtask_key)
        else:
            self.italic_notes.add(subtask_key)

    def delete_item(self, idx):
        todo_id, _ = self.todos[idx]
        del self.todos[idx]
        if todo_id in self.subtodos:
            del self.subtodos[todo_id]
        self.highlighted = {i for i in self.highlighted if i != f"{todo_id}" and not str(i).startswith(f"{todo_id}_")}
        self.priorities = {i for i in self.priorities if i != f"{todo_id}" and not str(i).startswith(f"{todo_id}_")}
        self.bold_notes = {i for i in self.bold_notes if i != f"{todo_id}" and not str(i).startswith(f"{todo_id}_")}
        self.italic_notes = {i for i in self.italic_notes if i != f"{todo_id}" and not str(i).startswith(f"{todo_id}_")}

    def delete_subitem(self, parent_id, sub_idx):
        if parent_id in self.subtodos and sub_idx < len(self.subtodos[parent_id]):
            del self.subtodos[parent_id][sub_idx]
            self.highlighted = {i for i in self.highlighted if i != f"{parent_id}_{sub_idx}"}
            self.priorities = {i for i in self.priorities if i != f"{parent_id}_{sub_idx}"}
            self.bold_notes = {i for i in self.bold_notes if i != f"{parent_id}_{sub_idx}"}
            self.italic_notes = {i for i in self.italic_notes if i != f"{parent_id}_{sub_idx}"}

    def handle_input(self, input_str):
        try:
            if input_str.isdigit():
                idx = int(input_str) - 1
                self.highlight_item(idx)
            elif input_str[0].isdigit() and input_str[1] == ' ':
                parts = input_str.split(' ', 1)
                if len(parts) == 2:
                    parent_idx = int(parts[0]) - 1
                    subitem = parts[1].strip()
                    self.add_subitem(self.todos[parent_idx][0], subitem)
            elif input_str[0].isdigit() and len(input_str) > 1 and input_str[1].isalpha():
                parent_idx = int(input_str[0]) - 1
                sub_idx = ord(input_str[1]) - 97
                self.highlight_subitem(self.todos[parent_idx][0], sub_idx)
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
            elif input_str.startswith(":b "):
                try:
                    idx = int(input_str[3:]) - 1
                    self.bold_item(idx)
                except ValueError:
                    pass
            elif input_str.startswith(":i "):
                try:
                    idx = int(input_str[3:]) - 1
                    self.italic_item(idx)
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
                            if range_str[0].isdigit() and len(range_str) > 1 and range_str[1].isalpha():
                                parent_idx = int(range_str[0]) - 1
                                sub_idx = ord(range_str[1]) - 97
                                self.delete_subitem(self.todos[parent_idx][0], sub_idx)
                            else:
                                indices.append(int(range_str) - 1)
                    for idx in sorted(indices, reverse=True):
                        self.delete_item(idx)
                except ValueError:
                    pass
            elif input_str.startswith(":theme "):
                theme_name = input_str[7:].strip().lower()
                self.apply_theme(theme_name)
            elif input_str.strip() == ":q":
                self.save_todos()
                return False  # Signal to exit the app
            elif input_str.strip() == ":s":
                self.save_to_http()
            elif input_str.strip() == ":check":
                if self.check_db_on_http():
                    self.stdscr.addstr(0, 0, "Database is present on HTTP server.", curses.color_pair(2))
                else:
                    self.stdscr.addstr(0, 0, "Database is not present on HTTP server.", curses.color_pair(2))
                self.stdscr.refresh()
                self.stdscr.getch()
            else:
                self.add_item(input_str)
            self.save_todos()  # Save todos after each modification
            return True
        except Exception as e:
            self.log_error(f"Error handling input: {e}")
            return True

    def get_suggestions(self, input_str):
        if input_str.startswith(":"):
            return [(cmd, desc) for cmd, desc in COMMANDS.items() if cmd.startswith(input_str)]
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
                    input_str = suggestions[selected_suggestion_index][0]
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
