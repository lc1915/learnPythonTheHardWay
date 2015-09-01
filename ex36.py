# write a simple game

print "You wake up in your dream"
sentence = '''
You find that you are in a magic world.
Those who have wings are flying around you.
They are calling your name.
'''

def talk():
	talk_choice = raw_input("> ")
	
	if "beautiful" in talk_choice:
		print "ahaha"
	elif "ugly" in talk_choice:
		print "died"

talk()
