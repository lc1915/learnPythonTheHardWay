# making decisions

print "You enter a dark room with two doors. Do you go through door #1 or do or #2?"

door = raw_input("> ")

if door == "1":
	print "There's a giant bear here eating a cheese cake. What do you do?"
	print "1. Take the cake."
	print "2. Scream at the bear."

	bear = raw_input("> ")

	if bear == "1":
		print "bear eats your face off!"
	elif bear == "2":
		print "bear eats your legs off!"
	else:
		print "Well, doing %s is better! Bear run away!" % bear

elif door == "2":
	print "You stare into the endless abyss at Cthulhu's retina."
	print "1. Blueberries."
	print "2. Yellow jacket clothespins."
	print "3. ahah"

	insanity = raw_input("> ")
	
	if insanity == "1" or insanity == "2":
		print "12"
	else:
		print "333"

else:
	print "You asdfasdfadf"

if door == "3":
    print "ahahah"
    print "you are so great!"
