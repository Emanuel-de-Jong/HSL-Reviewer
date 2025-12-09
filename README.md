# HSL Reviewer
Improve your shapes and intuition in the game of Go. Tailered to your weaknesses from your own games. Using human supervised learning for questions and answers of your skill level.

**Active Development:** 2024-03-26 - 2024-03-29<br>
**Last Change:** 2025-12-09<br>
**Highlights:** Machine Learning<br>

| | |
| :---: | :---: |
| ![](/Screenshots/1-Question.png) | ![](/Screenshots/2-Answer.png) |
| ![](/Screenshots/3-Reviewer.png) | |

X = Game move<br>
O = HSL move<br>

## Prerequisites
1. [KataGo](https://github.com/lightvector/KataGo/releases) with a [model](https://katagotraining.org/networks/).
2. A HSL model. For example [this model](https://cdn.discordapp.com/attachments/583775968804732928/1225481815033253969/b18c384nbt-humanv0.ckpt?ex=662149e1&is=660ed4e1&hm=ab95493b318a249923304d6e199c8db69b788929487557e316f97f6e82ec2259&) from lightvector. Check the [Discord server](https://discord.gg/utV9dsfqFW) for possibly newer versions.
3. Python. Version 3.10.6 works for me.
4. Run `pip install -r requirements.txt` to install the necessary python packages.
5. Install [PyTorch](https://pytorch.org/get-started/locally/).
6. Change the parameters in `Reviewer.sh/bat` to your own. If you're not sure about the device, `CPU` is a slow but safe bet. Format (SGF and PLAYER are optional): `[HSL_MODEL] [HSL_DEVICE] [KATAGO_EXE] [KATAGO_ANALYSIS_CFG] [KATAGO_MODEL] (SGF) (PLAYER)`

## Create flashcards
1. Run `Reviewer.sh/bat`.
2. Set the color you were in the game you want to review.
3. Optionally change the HSL sliders.
4. Drag & drop your game sgf.
5. Wait until the console says `=== REVIEW DONE ===`

There are also some options you can tweak at the top in `hsl_reviewer.py`.

## Train
1. Run `Trainer.sh/bat`.
2. Load a card and think of a move.
3. Click on the board to see the answer.
4. Delete the card if you feel the answer is easy.
5. Load the next card.
