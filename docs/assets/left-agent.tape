#
# VHS .tape file for generating a gif of an LLM playing Rogue.
#

Output left-agent.gif

Set FontSize 12
Set Width 750
Set Height 575
Set Padding 20

Hide
Type 'PS1="> "' Enter
Type "clear" Enter
Sleep 100 ms
Show

Type "uv run rogue-bench --player agent \"
Enter 
Type "--agent-class left.LeftAgent \"
Enter
Type "--agent-config config/left.json \"
Enter
Type "--seed 8"

Sleep 500ms

Enter

Sleep 10s

Ctrl+C
