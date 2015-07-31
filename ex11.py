#asking questions

print "How old are you?",
age = raw_input()
print "How tall are you?",
height = int(raw_input())
print "How much do you weigh?",
weight = raw_input()

print "So, you're %r old, %r tall and %r heavy." % (
    age, height, weight)
print "So, you're %s old, %d tall and %s heavy." % (
    age, height, weight)
