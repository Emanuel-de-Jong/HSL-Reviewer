import wx
import subprocess
import json
import sys
import os
from threading import Thread
import atexit
import datetime
import time
import math
import random
import string

from gamestate import GameState
from board import Board
from sgfmetadata import SGFMetadata
from query_analysis_engine_example import KataGo

from sgfmill import sgf, sgf_moves

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

GRID_SIZE = 7
GRID_RADIUS = math.floor(GRID_SIZE / 2)

MIN_SCORE_DIFF_ACTUAL_HSL = 2
MAX_SCORE_DIFF_ACTUAL_HSL = 10
MAX_SCORE_DIFF_HSL_KATA = 1

HSL_SOURCE = "OGS"
HSL_RANK = "2d"
HSL_DATE = 2022
HSL_TIME_CONTROL = "Slow"

HSL_ACTUAL_COMPARE_VISITS = 500
KATA_BEST_VISITS = 2_500

def interpolateColor(points,x):
    for i in range(len(points)):
        x1,c1 = points[i]
        if x < x1:
            if i <= 0:
                return c1
            x0,c0 = points[i-1]
            interp = (x-x0)/(x1-x0)
            return c0 + (c1-c0)*interp
    return points[-1][1]

POLICY_COLORS = [
  (0.00, np.array([100,0,0,15])),
  (0.35, np.array([184,0,0,255])),
  (0.50, np.array([220,0,0,255])),
  (0.65, np.array([255,100,0,255])),
  (0.85, np.array([205,220,60,255])),
  (0.94, np.array([120,235,130,255])),
  (1.00, np.array([100,255,245,255])),
]

def policy_color(prob):
    r,g,b,a = interpolateColor(POLICY_COLORS,prob**0.25)
    return (round(r), round(g), round(b), round(a))

def load_sgf_game_state(file_path):
    with open(file_path, 'rb') as f:
        game = sgf.Sgf_game.from_bytes(f.read())

    size = game.get_size()
    if size < 9 or size > 19:
        raise ValueError("Board size must be between 9 and 19 inclusive.")

    board, plays = sgf_moves.get_setup_and_moves(game)

    moves = []
    for x in range(size):
        for y in range(size):
            color = board.get(x, y)
            if color is not None:
                moves.append((y, 18 - x, (Board.BLACK if color == "b" else Board.WHITE)))

    for color, move in plays:
        if move is not None:
            x, y = move
            moves.append((y, 18 - x, (Board.BLACK if color == "b" else Board.WHITE)))

    game_state = GameState(size, GameState.RULES_JAPANESE)
    for (x,y,color) in moves:
        game_state.play(color, game_state.board.loc(x,y))

    return game_state

class GoBoard(wx.Panel):
    def __init__(self, parent, game_state, cell_size=30, margin=30):
        super().__init__(parent)
        self.game_state = game_state
        self.board_size = game_state.board.size
        self.cell_size = cell_size
        self.margin = margin

        self.should_draw_review_grid = False
        self.should_draw_review_moves = False

        self.sgfmeta = SGFMetadata()
        self.latest_model_response = None

        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_LEFT_UP, self.on_click)

    def get_desired_size(self):
        board_width = self.board_size * self.cell_size + 2 * self.margin
        board_height = self.board_size * self.cell_size + self.cell_size + 2 * self.margin
        return board_width, board_height

    def px_of_x(self, x):
        return round(self.cell_size * x + self.margin + self.cell_size / 2)
    def py_of_y(self, y):
        return round(self.cell_size * y + self.margin + self.cell_size + self.cell_size / 2)

    def x_of_px(self, px):
        return round((px - self.margin - self.cell_size / 2) / self.cell_size)
    def y_of_py(self, py):
        return round((py - self.margin - self.cell_size - self.cell_size / 2) / self.cell_size)

    def screenshot(self, filename):
        output_path = os.getcwd() + "/output"
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        filename += ".png"
        
        size = self.GetSize()
        bitmap = wx.Bitmap(size.width, size.height)
        mem_dc = wx.MemoryDC()
        mem_dc.SelectObject(bitmap)

        dc = wx.ClientDC(self)
        mem_dc.Blit(0, 0, size.width, size.height, dc, 0, 0)
        bitmap.SaveFile(output_path + "/" + filename, wx.BITMAP_TYPE_PNG)
        mem_dc.SelectObject(wx.NullBitmap)

    def on_paint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)

        gc.SetBrush(wx.Brush(wx.Colour(200, 150, 100)))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, self.GetSize().Width, self.GetSize().Height)

        gc.SetPen(wx.Pen(wx.BLACK, 1))

        for i in range(self.board_size):
            gc.StrokeLine(
                self.px_of_x(0),
                self.py_of_y(i),
                self.px_of_x(self.board_size - 1),
                self.py_of_y(i),
            )
            gc.StrokeLine(
                self.px_of_x(i),
                self.py_of_y(0),
                self.px_of_x(i),
                self.py_of_y(self.board_size - 1),
            )

        for x in range(self.board_size):
            for y in range(self.board_size):
                loc = self.game_state.board.loc(x, y)

                if self.game_state.board.board[loc] == Board.BLACK:
                    gc.SetBrush(wx.Brush(wx.BLACK))
                    gc.DrawEllipse(self.px_of_x(x) - (self.cell_size // 2 - 2), self.py_of_y(y) - (self.cell_size // 2 - 2), self.cell_size - 4, self.cell_size - 4)
                elif self.game_state.board.board[loc] == Board.WHITE:
                    gc.SetBrush(wx.Brush(wx.WHITE))
                    gc.DrawEllipse(self.px_of_x(x) - (self.cell_size // 2 - 2), self.py_of_y(y) - (self.cell_size // 2 - 2), self.cell_size - 4, self.cell_size - 4)

        gc.SetBrush(wx.Brush(wx.BLACK, wx.TRANSPARENT))
        
        if self.should_draw_review_grid:
            parent = self.GetParent().GetParent()

            gc.SetPen(wx.Pen(wx.BLUE, 4))
            x = self.px_of_x(max(parent.actual_move.x - GRID_RADIUS, 0)) - self.cell_size / 2
            y = self.py_of_y(max(parent.actual_move.y - GRID_RADIUS, 0)) - self.cell_size / 2
            w = self.px_of_x(min(parent.actual_move.x + GRID_RADIUS, 18)) - x + self.cell_size / 2
            h = self.py_of_y(min(parent.actual_move.y + GRID_RADIUS, 18)) - y + self.cell_size / 2
            gc.DrawRectangle(x, y, w, h)

            if self.should_draw_review_moves:
                gc.SetPen(wx.Pen(wx.BLACK, 4))
                gc.DrawEllipse(self.px_of_x(parent.hsl_move.x) - (self.cell_size // 2 - 6), self.py_of_y(parent.hsl_move.y) - (self.cell_size // 2 - 6), self.cell_size - 12, self.cell_size - 12)

                gc.SetFont(wx.Font(26, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL), wx.Colour(0, 0, 0, 100))
                gc.DrawText("x", self.px_of_x(parent.actual_move.x) - (self.cell_size // 2 - 7), self.py_of_y(parent.actual_move.y) - (self.cell_size // 2 + 7))

                # if (parent.kata_move != parent.hsl_move):
                #     gc.DrawRectangle(self.px_of_x(parent.kata_move.x) - (self.cell_size // 2 - 6), self.py_of_y(parent.kata_move.y) - (self.cell_size // 2 - 6), self.cell_size - 12, self.cell_size - 12)

        gc.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL), wx.Colour(0, 150, 0))
        label = " to play"
        if (self.GetParent().GetParent().player == "B"):
            label = "Black" + label
        else:
            label = "White" + label
        gc.DrawText(label, 255, 15)

        # Draw column labels
        gc.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL), wx.BLACK)
        for x in range(self.board_size):
            col_label = "ABCDEFGHJKLMNOPQRSTUVWXYZ"[x]
            text_width, text_height = gc.GetTextExtent(col_label)
            text_x = self.px_of_x(x) - text_width // 2
            gc.DrawText(col_label, text_x, self.py_of_y(-0.8)-text_height//2)
            gc.DrawText(col_label, text_x, self.py_of_y(self.board_size-0.2)-text_height//2)

        # Draw row labels
        for y in range(self.board_size):
            row_label = str(self.board_size - y)
            text_width, text_height = gc.GetTextExtent(row_label)
            text_y = self.py_of_y(y) - text_height // 2
            gc.DrawText(row_label, self.px_of_x(-0.8)-text_width//2, text_y)
            gc.DrawText(row_label, self.px_of_x(self.board_size-0.2)-text_width//2, text_y)


    def on_click(self, event):
        x = self.x_of_px(event.GetX())
        y = self.y_of_py(event.GetY())

        if 0 <= x < self.board_size and 0 <= y < self.board_size:
            loc = self.game_state.board.loc(x, y)
            pla = self.game_state.board.pla

            if self.game_state.board.would_be_legal(pla,loc):
                self.game_state.play(pla, loc)

                command = {"command": "play", "pla": pla, "loc": loc}
                parent = self.GetParent().GetParent()
                parent.send_command(parent.hsl_server_process, command)
                response = parent.receive_response(parent.hsl_server_process)
                if response != {"outputs": ""}:
                    parent.handle_error(f"Unexpected response from server: {response}")

                self.Refresh()
                self.refresh_model()

    def set_sgfmeta(self, sgfmeta):
        self.sgfmeta = sgfmeta

    def refresh_model(self):
        sgfmeta = self.sgfmeta
        command = {"command": "get_model_outputs", "sgfmeta": sgfmeta.to_dict()}
        parent = self.GetParent().GetParent()
        parent.send_command(parent.hsl_server_process, command)
        response = parent.receive_response(parent.hsl_server_process)
        if "outputs" not in response:
            parent.handle_error(f"Unexpected response from server: {response}")
        self.latest_model_response = response["outputs"]
        self.Refresh()


class LabeledSlider(wx.Panel):
    def __init__(self, parent, title, options, on_scroll_callback=None, start_option=None):
        super().__init__(parent)

        self.options = options
        self.on_scroll_callback = on_scroll_callback
        self.title = title
        self.is_extrapolation = False

        # Create the slider
        start_idx = 0 if start_option is None else options.index(start_option)
        self.slider = wx.Slider(self, value=start_idx, minValue=0, maxValue=len(options) - 1, style=wx.SL_HORIZONTAL | wx.SL_AUTOTICKS)
        self.slider.SetTickFreq(1)  # Set the tick frequency to 1
        self.slider.Bind(wx.EVT_SCROLL, self.on_slider_scroll)

        # Create the label to display the selected option
        self.label = wx.StaticText(self, label = self.title + ": " + str(self.options[start_idx]))

        font_size = 12

        font = self.label.GetFont()
        font.SetPointSize(font_size)
        self.label.SetFont(font)
        font = self.slider.GetFont()
        font.SetPointSize(font_size)
        self.slider.SetFont(font)

        # Create a sizer to arrange the widgets
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.label, 0, wx.ALIGN_LEFT | wx.ALL, 10)
        sizer.Add(self.slider, 0, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(sizer)

    def get_selected_index(self):
        return self.slider.GetValue()

    def get_selected_option(self):
        selected_index = self.get_selected_index()
        return self.options[selected_index]

    def refresh_label(self):
        option_index = self.slider.GetValue()
        selected_option = self.options[option_index]
        self.label.SetLabel(self.title + ": " + str(selected_option) + ("" if not self.is_extrapolation else " (No Training Data)"))

    def set_is_extrapolation(self, b):
        if self.is_extrapolation != b:
            self.is_extrapolation = b
            self.refresh_label()

    def on_slider_scroll(self, event):
        option_index = self.slider.GetValue()
        selected_option = self.options[option_index]
        self.refresh_label()
        if self.on_scroll_callback:
            self.on_scroll_callback(option_index, selected_option)


class SliderWindow(wx.Frame):
    def __init__(self, parent):
        super().__init__(parent, title="Sliders")
        panel = wx.Panel(self)
        panel_sizer = wx.BoxSizer(wx.VERTICAL)
        panel_sizer.Add(400,0,0)

        self.source_slider = LabeledSlider(panel, title="Source", options=["KG","OGS","KGS","Fox","Tygem(Unused)","GoGoD","Go4Go"],
            on_scroll_callback = (lambda idx, option: self.update_metadata()),
            start_option=HSL_SOURCE,
        )
        panel_sizer.Add(self.source_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.rank_slider = LabeledSlider(panel, title="Rank", options=[
            "KG","9d","8d","7d","6d","5d","4d","3d","2d","1d","1k","2k","3k","4k","5k","6k","7k","8k","9k","10k","11k","12k","13k","14k","15k","16k","17k","18k","19k","20k"
            ],
            on_scroll_callback = (lambda idx, option: self.update_metadata()),
            start_option=HSL_RANK,
        )
        panel_sizer.Add(self.rank_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.date_slider = LabeledSlider(panel, title="Date", options=[
            1800,1825,1850,1875,1900,1915,1930,1940,1950,1960,1970,1980,1985,1990,1995,2000,2005,2008,2010,2012,2013,2014,2015,2016,2017,2018,2019,2020,2021,2022,2023],
            on_scroll_callback = (lambda idx, option: self.update_metadata()),
            start_option=HSL_DATE,
        )
        panel_sizer.Add(self.date_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.tc_slider = LabeledSlider(panel, title="TimeControl", options=["Blitz","Fast","Slow","Unknown"],
            on_scroll_callback = (lambda idx, option: self.update_metadata()),
            start_option=HSL_TIME_CONTROL,
        )
        panel_sizer.Add(self.tc_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)


        panel.SetSizer(panel_sizer)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(sizer)

        self.Bind(wx.EVT_CLOSE, self.on_close)

    def on_close(self, event):
        self.GetParent().hsl_server_process.terminate()
        self.GetParent().kata_server.close()
        self.GetParent().Close()

    def update_metadata(self):
        sgfmeta = SGFMetadata(
            inverseBRank = self.rank_slider.get_selected_index(),
            inverseWRank = self.rank_slider.get_selected_index(),
            bIsHuman = self.rank_slider.get_selected_index() != 0,
            wIsHuman = self.rank_slider.get_selected_index() != 0,
            gameIsUnrated = False,
            gameRatednessIsUnknown = self.source_slider.get_selected_option() == "KGS",
            tcIsUnknown = self.tc_slider.get_selected_option() == "Unknown",
            tcIsByoYomi = self.tc_slider.get_selected_option() != "Unknown",
            mainTimeSeconds = [300,900,1800,0][self.tc_slider.get_selected_index()],
            periodTimeSeconds = [10,15,30,0][self.tc_slider.get_selected_index()],
            byoYomiPeriods = [5,5,5,0][self.tc_slider.get_selected_index()],
            boardArea = 361,
            gameDate = datetime.date(self.date_slider.get_selected_option(),6,1),
            source = self.source_slider.get_selected_index(),
        )

        source = self.source_slider.get_selected_option()
        if source == "KG":
            self.rank_slider.set_is_extrapolation(self.rank_slider.get_selected_index() != 0)
            self.tc_slider.set_is_extrapolation(self.tc_slider.get_selected_option() == "Unknown")
            self.date_slider.set_is_extrapolation(self.date_slider.get_selected_option() < 2022)
        elif source == "OGS":
            self.rank_slider.set_is_extrapolation(self.rank_slider.get_selected_index() == 0)
            self.tc_slider.set_is_extrapolation(self.tc_slider.get_selected_option() == "Unknown")
            self.date_slider.set_is_extrapolation(self.date_slider.get_selected_option() < 2007)
        elif source == "KGS":
            self.rank_slider.set_is_extrapolation(self.rank_slider.get_selected_index() == 0)
            self.tc_slider.set_is_extrapolation(self.tc_slider.get_selected_option() == "Unknown")
            self.date_slider.set_is_extrapolation(self.date_slider.get_selected_option() < 2016)
        elif source == "Fox":
            self.rank_slider.set_is_extrapolation(self.rank_slider.get_selected_index() == 0 or self.rank_slider.get_selected_index() >= 28)
            self.tc_slider.set_is_extrapolation(self.tc_slider.get_selected_option() == "Unknown")
            self.date_slider.set_is_extrapolation(self.date_slider.get_selected_option() < 2014 or self.date_slider.get_selected_option() > 2019)
        elif source == "Tygem(Unused)":
            self.rank_slider.set_is_extrapolation(True)
            self.tc_slider.set_is_extrapolation(True)
            self.date_slider.set_is_extrapolation(True)
        elif source == "GoGoD":
            self.rank_slider.set_is_extrapolation(self.rank_slider.get_selected_index() == 0 or self.rank_slider.get_selected_index() > 5)
            self.tc_slider.set_is_extrapolation(self.tc_slider.get_selected_option() != "Unknown")
            self.date_slider.set_is_extrapolation(self.date_slider.get_selected_option() > 2020)
        elif source == "Go4Go":
            self.rank_slider.set_is_extrapolation(self.rank_slider.get_selected_index() != 1)
            self.tc_slider.set_is_extrapolation(self.tc_slider.get_selected_option() != "Unknown")
            self.date_slider.set_is_extrapolation(self.date_slider.get_selected_option() < 2020)

        self.GetParent().board.set_sgfmeta(sgfmeta)
        self.GetParent().board.refresh_model()

class Coord():
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def __eq__(self, other):
        if isinstance(other, Coord):
            return self.x == other.x and self.y == other.y
        return False
    
    def __str__(self):
        return f"({self.x}, {self.y})"

class ColorButtons(wx.Panel):
    def __init__(self, parent, player):
        super().__init__(parent)

        vbox = wx.BoxSizer(wx.VERTICAL)
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        self.radio_button_black = wx.RadioButton(self, label="Black")
        hbox.Add(self.radio_button_black, proportion=0, flag=wx.ALIGN_LEFT, border=5)

        self.radio_button_white = wx.RadioButton(self, label="White")
        hbox.Add(self.radio_button_white, proportion=0, flag=wx.ALIGN_LEFT, border=5)

        vbox.Add(hbox, proportion=0, flag=wx.EXPAND | wx.ALL, border=5)
        self.SetSizer(vbox)

        self.radio_button_black.Bind(wx.EVT_RADIOBUTTON, self.on_radio_button_black_select)
        self.radio_button_white.Bind(wx.EVT_RADIOBUTTON, self.on_radio_button_white_select)

        if player == "W":
            self.radio_button_white.SetValue(True)

    def on_radio_button_black_select(self, event):
        self.GetParent().GetParent().player = "B"

    def on_radio_button_white_select(self, event):
        self.GetParent().GetParent().player = "W"

class FileDropTarget(wx.FileDropTarget):
    def __init__(self, window):
        super().__init__()
        self.window = window

    def OnDropFiles(self, x, y, sgf_files):
        thread = Thread(target=lambda: self.window.on_drop_files(sgf_files))
        thread.start()
        return True

class GoClient(wx.Frame):
    def loc_state_to_coord(self, state):
        return Coord(self.game_state.board.loc_x(state), self.game_state.board.loc_y(state))

    def loc_coord_to_state(self, coord):
        return self.game_state.board.loc(coord.x, coord.y)

    def loc_kata_to_coord(self, kata):
        chars = [char for char in kata]

        x = ord(chars[0])
        # 'I' is skipped
        if x <= 72:
            x -= 65
        else:
            x -= 66
            
        return Coord(x, 19 - int(''.join(chars[1:])))

    def loc_coord_to_kata(self, coord):
        return "ABCDEFGHJKLMNOPQRSTUVWXYZ"[coord.x] + str(19 - coord.y)
    
    def loc_state_to_kata(self, state):
        return self.loc_coord_to_kata(self.loc_state_to_coord(state))
    
    def loc_kata_to_state(self, kata):
        return self.loc_coord_to_state(self.loc_kata_to_coord(kata))

    def __init__(self, hsl_model_path, hsl_device, katago_exe_path, katago_analysis_cfg_path, katago_model_path, game_state, player):
        super().__init__(parent=None, title="HumanSLNetViz")
        self.hsl_model_path = hsl_model_path
        self.hsl_device = hsl_device

        self.katago_exe_path = katago_exe_path
        self.katago_analysis_cfg_path = katago_analysis_cfg_path
        self.katago_model_path = katago_model_path

        self.game_state = game_state
        self.board_size = self.game_state.board_size

        self.player = player

        self.SetDropTarget(FileDropTarget(self))

        self.hsl_server_process = self.start_server()
        self.init_server(self.hsl_server_process)

        self.start_kata_server()

        self.init_ui()
        
        self.undo(len(self.game_state.moves))

        if len(self.game_state.redo_stack) > 0:
            review_thread = Thread(target=lambda: self.review())
            review_thread.start()
    
    def review(self):
        time.sleep(2)

        while len(self.game_state.redo_stack) > 1:
            self.redo()

            move_state_player = self.game_state.redo_stack[-1][0][0]
            if self.player == "B" and move_state_player == 2 or self.player == "W" and move_state_player == 1:
                continue

            moves_and_probs0 = self.board.latest_model_response["moves_and_probs0"]

            highest_hsl_val = 0
            highest_hsl_loc = 0
            for prob in moves_and_probs0:
                if prob[1] > highest_hsl_val:
                    highest_hsl_val = prob[1]
                    highest_hsl_loc = prob[0]
            
            self.hsl_move = self.loc_state_to_coord(highest_hsl_loc)
            self.actual_move = self.loc_state_to_coord(self.game_state.redo_stack[-1][0][1])

            if self.hsl_move == self.actual_move:
                continue

            if abs(self.hsl_move.x - self.actual_move.x) > GRID_RADIUS or abs(self.hsl_move.y - self.actual_move.y) > GRID_RADIUS:
                continue

            hsl_score = self.get_kata_score_lead(HSL_ACTUAL_COMPARE_VISITS, [self.hsl_move])[0][1]
            actual_score = self.get_kata_score_lead(HSL_ACTUAL_COMPARE_VISITS, [self.actual_move])[0][1]

            # print(f"HSL= {str(self.hsl_move)}: {hsl_score:.2f} | Actual= {str(self.actual_move)}: {actual_score:.2f}")
            
            if self.player == "B":
                if (hsl_score - MIN_SCORE_DIFF_ACTUAL_HSL) < actual_score or (hsl_score - MAX_SCORE_DIFF_ACTUAL_HSL) > actual_score:
                    continue
            else:
                if (hsl_score + MIN_SCORE_DIFF_ACTUAL_HSL) > actual_score or (hsl_score + MAX_SCORE_DIFF_ACTUAL_HSL) < actual_score:
                    continue

            allow_moves = []
            for x in range(max(self.actual_move.x - GRID_RADIUS, 0), min(self.actual_move.x + GRID_RADIUS, 18) + 1):
                for y in range(max(self.actual_move.y - GRID_RADIUS, 0), min(self.actual_move.y + GRID_RADIUS, 18) + 1):
                    allow_moves.append(Coord(x, y))
            
            kata_score = self.get_kata_score_lead(KATA_BEST_VISITS, allow_moves)[0][1]

            if abs(kata_score - hsl_score) > MAX_SCORE_DIFF_HSL_KATA:
                continue

            rnd_filename = ''.join(random.choices(string.ascii_letters + string.digits, k=6))

            self.board.should_draw_review_grid = True
            self.board.Refresh()
            time.sleep(0.25)
            self.board.screenshot(rnd_filename + "_1")

            self.board.should_draw_review_moves = True
            self.board.Refresh()
            time.sleep(0.25)
            self.board.screenshot(rnd_filename + "_2")
            
            self.board.should_draw_review_grid = False
            self.board.should_draw_review_moves = False
        
        print("=== REVIEW DONE ===")

    def init_ui(self):
        color_buttons_panel = wx.Panel(self)
        self.color_buttons = ColorButtons(color_buttons_panel, self.player)
        color_buttons_sizer = wx.BoxSizer(wx.VERTICAL)
        color_buttons_sizer.Add(self.color_buttons, proportion=0, flag=wx.EXPAND | wx.ALL)
        color_buttons_panel.SetSizer(color_buttons_sizer)

        board_panel = wx.Panel(self)
        self.board = GoBoard(board_panel, self.game_state)
        board_sizer = wx.BoxSizer(wx.VERTICAL)
        board_sizer.Add(self.board, proportion=1, flag=wx.EXPAND | wx.ALL)
        board_panel.SetSizer(board_sizer)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_down)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(color_buttons_panel, proportion=0, flag=wx.EXPAND | wx.ALL)
        main_sizer.Add(board_panel, proportion=1, flag=wx.EXPAND | wx.ALL)

        self.SetSizer(main_sizer)
        main_sizer.Fit(self)

        board_width, board_height = self.board.get_desired_size()
        self.SetClientSize(board_width, board_height + self.color_buttons.GetSize().GetHeight())
        screen_width, screen_height = wx.DisplaySize()
        frame_width, frame_height = self.GetSize()
        pos_x = (screen_width - frame_width) // 2 - 300
        pos_y = (screen_height - frame_height) // 2
        self.SetPosition((pos_x, pos_y))

        self.slider_window = SliderWindow(self)
        frame_width, frame_height = self.slider_window.GetSize()
        pos_x = (screen_width - frame_width) // 2 + 240
        pos_y = (screen_height - frame_height) // 2
        self.slider_window.SetPosition((pos_x, pos_y))


    def start_server(self):
        # print(f"Starting hsl server with command: {server_command}")
        server_process = subprocess.Popen(
            f"python humanslnet_server.py -checkpoint {self.hsl_model_path} -device {self.hsl_device}",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        atexit.register(server_process.terminate)

        def print_stderr():
            while True:
                line = server_process.stderr.readline()
                if not line:
                    returncode = server_process.poll()
                    if returncode is not None:
                        return
                print(line,end="")

        t = Thread(target=print_stderr)
        t.daemon = True
        t.start()

        return server_process

    def init_server(self, server_process):
        command = {"command": "start", "board_size": self.board_size, "rules": GameState.RULES_JAPANESE}
        self.send_command(server_process, command)
        response = self.receive_response(server_process)
        if response != {"outputs": ""}:
            self.handle_error(f"Unexpected response from server: {response}")

        for (pla,loc) in self.game_state.moves:
            command = {"command": "play", "pla": pla, "loc": loc}
            self.send_command(server_process, command)
            response = self.receive_response(server_process)
            if response != {"outputs": ""}:
                self.handle_error(f"Unexpected response from server: {response}")

    def start_kata_server(self):
        self.kata_server = KataGo(self.katago_exe_path,
                                  self.katago_analysis_cfg_path,
                                  self.katago_model_path)
        
        atexit.register(self.kata_server.close)
    
    def get_kata_score_lead(self, max_visits, allow_moves = [], avoid_moves = []):
        moves = []
        for pla, loc in self.game_state.moves:
            color = "b"
            if (pla == 2):
                color = "w"
            
            move = self.loc_state_to_kata(loc)
            moves.append((color, move))

        query = {
            "id": str(self.kata_server.query_counter),
            "moves": moves,
            "rules": "Japanese",
            "komi": 6.5,
            "boardXSize": 19,
            "boardYSize": 19,
            "maxVisits": max_visits
        }
        self.kata_server.query_counter += 1

        if allow_moves:
            query["allowMoves"] = [{
                "player": self.player,
                "moves": [self.loc_coord_to_kata(coord) for coord in allow_moves],
                "untilDepth": 1
            }]
        
        if avoid_moves:
            query["avoidMoves"] = [{
                "player": self.player,
                "moves": [self.loc_coord_to_kata(coord) for coord in avoid_moves],
                "untilDepth": 1
            }]

        result = self.kata_server.query_raw(query)["moveInfos"]

        result_by_score = None
        if self.player == "B":
            result_by_score = sorted(result, key=lambda x: x["scoreLead"], reverse=True)
        else:
            result_by_score = sorted(result, key=lambda x: x["scoreLead"])

        output = []
        best_score = result_by_score[0]["scoreLead"]
        for move in result_by_score:
            if abs(move["scoreLead"] - best_score) > 1:
                break

            output.append((self.loc_kata_to_coord(move["move"]), move["scoreLead"]))

        return output

    def send_command(self, server_process, command):
        # print(f"Sending: {json.dumps(command)}")
        server_process.stdin.write(json.dumps(command) + "\n")
        server_process.stdin.flush()

    def receive_response(self, server_process):
        # print(f"Waiting for response")
        while True:
            returncode = server_process.poll()
            if returncode is not None:
                raise OSError(f"Server terminated unexpectedly with {returncode=}")
            response = server_process.stdout.readline().strip()
            if response != "":
                break
        # print(f"Got response (first 100 chars): {str(response[:100])}")
        return json.loads(response)

    def handle_error(self, error_message):
        print(f"Error: {error_message}")
        self.hsl_server_process.terminate()
        self.kata_server.close()

        sys.exit(1)

    def on_key_down(self, event):
        key_code = event.GetKeyCode()
        if (key_code == wx.WXK_LEFT or key_code == wx.WXK_BACK) and event.ShiftDown():
            self.undo(10)
        elif key_code == wx.WXK_LEFT or key_code == wx.WXK_BACK:
            self.undo()
        elif key_code == wx.WXK_RIGHT and event.ShiftDown():
            self.redo(10)
        elif key_code == wx.WXK_RIGHT:
            self.redo()
        elif key_code == wx.WXK_DOWN:
            self.undo(len(self.game_state.moves))
        elif key_code == wx.WXK_UP:
            self.redo(len(self.game_state.redo_stack))
        event.Skip()

    def undo(self, undo_count = 1):
        is_refresh_needed = False
        for i in range(undo_count):
            if not self.game_state.can_undo():
                break
            
            is_refresh_needed = True

            self.game_state.undo()

            command = {"command": "undo"}
            self.send_command(self.hsl_server_process, command)
            response = self.receive_response(self.hsl_server_process)
            if response != {"outputs": ""}:
                self.handle_error(f"Unexpected response from server: {response}")

        if is_refresh_needed:
            self.board.Refresh()
            self.board.refresh_model()

    def redo(self, redo_count = 1):
        is_refresh_needed = False
        for i in range(redo_count):
            if not self.game_state.can_redo():
                break
            
            is_refresh_needed = True

            self.game_state.redo()

            command = {"command": "redo"}
            self.send_command(self.hsl_server_process, command)
            response = self.receive_response(self.hsl_server_process)
            if response != {"outputs": ""}:
                self.handle_error(f"Unexpected response from server: {response}")

        if is_refresh_needed:
            self.board.Refresh()
            self.board.refresh_model()
    
    def on_drop_files(self, sgf_files):
        for sgf_file in sgf_files:
            game_state = load_sgf_game_state(sgf_file)
            
            self.game_state = game_state
            self.board_size = self.game_state.board_size

            self.board.game_state = game_state
            self.board.board_size = self.board_size

            self.init_server(self.hsl_server_process)
            self.undo(len(self.game_state.moves))

            self.board.Refresh()
            self.board.refresh_model()

            self.review()

    def on_close(self, event):
        self.hsl_server_process.terminate()
        self.kata_server.close()
        event.Skip()

def main():
    # hsl_reviewer [HSL_MODEL] [HSL_DEVICE] [KATAGO_EXE] [KATAGO_ANALYSIS_CFG] [KATAGO_MODEL] (SGF) (PLAYER)
    game_state = GameState(19, GameState.RULES_JAPANESE)
    if len(sys.argv) > 6:
        game_state = load_sgf_game_state(sys.argv[6])

    player = "B"
    if len(sys.argv) > 7:
        player = sys.argv[7]

    app = wx.App()
    client = GoClient(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], game_state, player)
    client.Bind(wx.EVT_CLOSE, client.on_close)
    client.Show()
    client.slider_window.Show()
    client.slider_window.update_metadata()

    app.MainLoop()

if __name__ == "__main__":
    main()
