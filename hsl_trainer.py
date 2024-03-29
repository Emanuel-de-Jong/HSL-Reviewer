import wx
import os
import random

class HSLTrainer(wx.Frame):
    def __init__(self, parent, title):
        super(HSLTrainer, self).__init__(parent, title=title, size=(670, 800))

        self.panel = wx.Panel(self)
        self.flashcard_image = wx.StaticBitmap(self.panel)
        self.load_button = wx.Button(self.panel, label="Load Card")
        self.load_button.Bind(wx.EVT_BUTTON, self.on_load_button)
        self.delete_button = wx.Button(self.panel, label="Delete Card")
        self.delete_button.Bind(wx.EVT_BUTTON, self.on_delete_button)
        self.flashcard_image.Bind(wx.EVT_LEFT_DOWN, self.show_answer)
        self.question_file = None
        self.answer_file = None

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.button_sizer.Add(self.load_button, proportion=0, flag=wx.CENTER | wx.ALL, border=10)
        self.button_sizer.Add(self.delete_button, proportion=0, flag=wx.CENTER | wx.ALL, border=10)
        self.sizer.Add(self.flashcard_image, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        self.sizer.Add(self.button_sizer, proportion=0, flag=wx.CENTER | wx.ALL, border=10)

        self.panel.SetSizerAndFit(self.sizer)
        self.Show()

    def on_load_button(self, event):
        self.question_file, self.answer_file = self.select_random_files()
        if self.question_file and os.path.exists(self.question_file):
            question_image = wx.Image(self.question_file, wx.BITMAP_TYPE_ANY)
            self.flashcard_image.SetBitmap(wx.Bitmap(question_image))
        else:
            wx.MessageBox("No more flashcards to learn!", "Error", wx.OK | wx.ICON_ERROR)
            self.question_file = None
            self.answer_file = None

        self.Layout()

    def on_delete_button(self, event):
        if self.answer_file and os.path.exists(self.answer_file):
            os.remove(self.answer_file)
        if self.question_file and os.path.exists(self.question_file):
            os.remove(self.question_file)
        self.flashcard_image.SetBitmap(wx.Bitmap())
        self.question_file = None
        self.answer_file = None
        wx.MessageBox("Card deleted successfully!", "Success", wx.OK | wx.ICON_INFORMATION)

    def show_answer(self, event):
        if self.answer_file:
            answer_image = wx.Image(self.answer_file, wx.BITMAP_TYPE_ANY)
            self.flashcard_image.SetBitmap(wx.Bitmap(answer_image))

    def select_random_files(self):
        folder_path = os.getcwd() + "/output"
        files = os.listdir(folder_path)
        question_files = [file for file in files if file.endswith("_1.png")]
        answer_files = [file for file in files if file.endswith("_2.png")]

        if not question_files or not answer_files:
            wx.MessageBox("No flashcards found in the folder!", "Error", wx.OK | wx.ICON_ERROR)
            return None, None

        question_file = os.path.join(folder_path, random.choice(question_files))
        answer_file = os.path.join(folder_path, question_file.split("_1.png")[0] + "_2.png")

        return question_file, answer_file

if __name__ == "__main__":
    app = wx.App()
    HSLTrainer(None, title="HSL Trainer")
    app.MainLoop()
