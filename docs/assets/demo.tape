#
# VHS .tape file for generating a gif of an LLM playing Rogue.
#

Output demo.gif

Set FontSize 12
Set Width 750
Set Height 650
Set Padding 20

Hide
Type 'PS1="> "' Enter
Type "clear" Enter
Sleep 100 ms
Show

Type "uv run rogue-bench --player agent --agent-class naive.NaiveAgent --seed 9"

Sleep 500ms

Enter

Sleep 30s

Ctrl+C
