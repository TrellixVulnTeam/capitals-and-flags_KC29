import sys
import requests
import urllib.request
import bs4
import pickle
import os.path

from random import shuffle
from kivy.clock import Clock
from kivy.app import App
from kivy.core.window import Window
from kivy.properties import ObjectProperty
from kivy.uix.screenmanager import ScreenManager, Screen

CAPITALS_URL = "https://sv.wikipedia.org/wiki/Lista_över_huvudstäder"
FLAGS_URL = "https://sv.wikipedia.org/wiki/Lista_över_nationalflaggor"
WIKIPEDIA_BASE_URL = "https://sv.wikipedia.org/wiki/"

ENTRY_SIZE = 3
COUNTRY_COLUMN = 2
CAPITAL_COLUMN = 0

COLOR_CORRECT_ANSWER = 0, 0.737, 0.133, 1
COLOR_WRONG_ANSWER = 1, 0, 0, 1

DATA_FILE_NAME = "data.pickle"


class WelcomeScreen(Screen):
    def __init__(self, name):
        super(WelcomeScreen, self).__init__(name=name)
        Clock.schedule_once(self.transition_to_menu_screen, 2)

    def transition_to_menu_screen(self, *args):
        app = App.get_running_app()
        app.sm.transition.direction = "left"
        app.sm.current = "menu"


class MenuScreen(Screen):
    start_slider = ObjectProperty(None)
    stop_slider = ObjectProperty(None)

    def get_slider_values(self):
        return self.start_slider.value, self.stop_slider.value


class ResultScreen(Screen):
    result_label = ObjectProperty(None)
    retry_button = ObjectProperty(None)

    def display_result(self, num_correct_answers, num_questions):
        self.result_label.text = f"Antal rätt: {num_correct_answers} av {num_questions}\n"
        if num_correct_answers == num_questions:
            self.retry_button.disabled = True


class VocabularyQuizScreen(Screen):
    question_label = ObjectProperty(None)
    result_label = ObjectProperty(None)
    text_input = ObjectProperty(None)

    def update_question(self, question):
        self.question_label.text = question
        self.text_input.text = ""

    def get_answer(self):
        answer = self.ids.text_input.text
        self.text_input.text = ""
        self.schedule_text_input_focus()
        return answer

    def schedule_text_input_focus(self):
        Clock.schedule_once(self.focus_on_text_input, 0.1)

    def focus_on_text_input(self, *args):
        self.text_input.disabled = False
        self.text_input.focus = True

    def schedule_text_input_unfocus(self):
        Clock.schedule_once(self.unfocus_on_text_input, 0.1)

    def unfocus_on_text_input(self, *args):
        self.text_input.disabled = True
        self.text_input.focus = False

    def set_answer_correct(self):
        self.result_label.text = "Korrekt!"
        self.result_label.color = COLOR_CORRECT_ANSWER

    def set_answer_incorrect(self, question, correct_answer):
        self.result_label.text = f"{question} - {correct_answer}"
        self.result_label.color = COLOR_WRONG_ANSWER

    def clean(self):
        self.result_label.text = ""
        self.text_input.text = ""
        self.question_label.text = ""
        self.schedule_text_input_unfocus()


class FlashcardsQuizScreen(Screen):
    question_label = ObjectProperty(None)

    def __init__(self, name):
        super(FlashcardsQuizScreen, self).__init__(name=name)

    def toggle_button_pressed(self, state):
        app = App.get_running_app()
        self.question_label.text = app.answer if state == "down" else app.question

    def update_question(self, question):
        self.question_label.text = question


class FlagsQuizScreen(Screen):
    hint_label = ObjectProperty(None)
    flag = ObjectProperty(None)

    def toggle_button_pressed(self, state):
        if state == "normal":
            self.hint_label.text = ""
        else:
            app = App.get_running_app()
            self.hint_label.text = app.question

    def update_question(self, question):
        self.flag.source = "flags/" + question + ".png"
        self.hint_label.text = ""


class QuizApp(App):
    def __init__(self):
        super(QuizApp, self).__init__()
        self.capitals = []
        self.countries = []
        self.capital_to_country = {}
        self.country_to_capital = {}
        self.quiz_topic = ""
        self.quiz_type = ""

        self.load_data()
        self.num_loaded_questions = len(self.countries)
        if self.num_loaded_questions == 0:
            print("No questions found", file=sys.stderr)
            exit(1)

    def build(self):
        Window.size = (600, 450)

        self.welcome_screen = WelcomeScreen(name="welcome")
        self.start_screen = MenuScreen(name="menu")
        self.quiz_screen = None
        self.quiz_screen_vocabulary = VocabularyQuizScreen(name="glosor")
        self.quiz_screen_flashcards = FlashcardsQuizScreen(name="flashcards")
        self.quiz_screen_flags = FlagsQuizScreen(name="flags")
        self.result_screen = ResultScreen(name="result")

        sm = ScreenManager()
        sm.add_widget(self.welcome_screen)
        sm.add_widget(self.start_screen)
        sm.add_widget(self.quiz_screen_vocabulary)
        sm.add_widget(self.quiz_screen_flashcards)
        sm.add_widget(self.quiz_screen_flags)
        sm.add_widget(self.result_screen)
        self.sm = sm

        return sm

    def start_quiz(self):
        if not self.quiz_type or not self.quiz_topic:
            return

        if self.quiz_topic == "Länder":
            questions = self.countries
            answers = self.country_to_capital
        elif self.quiz_topic == "Huvudstäder":
            questions = self.capitals
            answers = self.capital_to_country
        elif self.quiz_topic == "Flaggor":
            questions = self.countries
            answers = []

        if self.quiz_type == "Glosor":
            self.quiz_screen = self.quiz_screen_vocabulary
        else:
            if self.quiz_topic == "Flaggor":
                self.quiz_screen = self.quiz_screen_flags
            else:
                self.quiz_screen = self.quiz_screen_flashcards

        start, stop = self.start_screen.get_slider_values()
        self._start_quiz(questions[start-1:stop], answers)

    def _start_quiz(self, questions, answers_dict):
        self.questions = questions.copy()
        self.num_questions = len(self.questions)
        shuffle(self.questions)

        self.answers_dict = answers_dict
        self.correct_answers_counter = 0
        self.wrong_answers = []

        self.question_counter = 0
        self.next_question()

        self.sm.transition.direction = "left"
        if self.quiz_topic == "Flaggor":
            self.sm.current = self.quiz_screen_flags.name
        else:
            self.sm.current = self.quiz_type.lower()

    def next_question(self):
        self.question = self.questions.pop()
        if self.quiz_topic == "Flaggor":
            self.answer = self.question
        else:
            self.quiz_screen.update_question(self.question)
            self.answer = self.answers_dict[self.question]

        self.question_counter = self.question_counter + 1
        self.quiz_screen.update_question(self.question)
        self.update_title()

    def update_title(self):
        if self.question_counter == 0:
            correct_ratio = 0
        else:
            correct_ratio = int(self.correct_answers_counter / self.question_counter * 100)
        self.title = f"Fråga: {self.question_counter}/{self.num_questions}, Rätt: {correct_ratio}%"

    def check_answer(self):
        answer = self.quiz_screen.get_answer()
        correct_answer = self.answers_dict[self.question]

        if answer.lower() == correct_answer.lower():
            self.correct_answers_counter = self.correct_answers_counter + 1
            self.quiz_screen.set_answer_correct()
        else:
            self.wrong_answers.append(self.question)
            self.quiz_screen.set_answer_incorrect(self.question, correct_answer)

        if self.questions:
            self.next_question()
        else:
            self.end_quiz()

    def end_quiz(self):
        if self.quiz_type == "Glosor":
            # Delayed transition to give the user time to read the result from the last question
            self.quiz_screen.schedule_text_input_unfocus()
            Clock.schedule_once(self.transition_to_result_screen, 1)
        else:
            self.transition_to_result_screen()

    def transition_to_result_screen(self, *args):
        self.sm.transition.direction = "left"
        self.sm.current = "result"

    def retry_quiz(self):
        self._start_quiz(self.wrong_answers, self.answers_dict)

    def load_data(self):
        if os.path.isfile(DATA_FILE_NAME):
            self.unpickle_data()
        else:
            self.download_data()

    def download_data(self):
        res = self.download_webbpage(CAPITALS_URL)
        soup = bs4.BeautifulSoup(res.text, "html.parser")
        elements = soup.select("td")

        for i in range(0, len(elements), ENTRY_SIZE):
            country = elements[i + COUNTRY_COLUMN].get_text().strip()
            capital = elements[i + CAPITAL_COLUMN].get_text().strip()

            self.capitals.append(capital)
            self.countries.append(country)

            self.capital_to_country[capital] = country
            self.country_to_capital[country] = capital

        self.download_flags()
        self.pickle_data()

    def download_webbpage(self, url):
        res = requests.get(url)
        try:
            res.raise_for_status()
        except requests.HTTPError as e:
            print(f"Couldn't download data: {e}")
            exit(1)
        return res

    def download_flags(self):
        if not os.path.isdir("flags"):
            os.makedirs("flags")

        for country in self.countries:
            file_path = os.path.join("flags", country + ".png")
            if os.path.isfile(file_path):
                continue

            res = self.download_webbpage(WIKIPEDIA_BASE_URL + country)
            soup = bs4.BeautifulSoup(res.text, "html.parser")
            element = soup.find("img", "thumbborder")
            url = "https:" + element["src"].replace("125px", "250px")
            urllib.request.urlretrieve(url, "flags/" + country + ".png")

    def pickle_data(self):
        data = {"countries": self.countries,
                "capitals": self.capitals,
                "country_to_capital": self.country_to_capital,
                "capital_to_country": self.capital_to_country}

        with open(DATA_FILE_NAME, "wb") as outfile:
            pickle.dump(data, outfile)

    def unpickle_data(self):
        with open(DATA_FILE_NAME, "rb") as infile:
            data = pickle.load(infile)
            self.countries = data["countries"]
            self.capitals = data["capitals"]
            self.country_to_capital = data["country_to_capital"]
            self.capital_to_country = data["capital_to_country"]
