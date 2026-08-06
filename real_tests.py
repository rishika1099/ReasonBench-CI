"""Real reasoning test suite: every item has a verifiable answer.

Categories mirror the taxonomy in the README. Each test is checked by exact
match on a normalized extracted answer, so scoring is measurement, not judgment.
"""

# (id, category, prompt, expected_answer)
# expected_answer is compared case-insensitively after stripping punctuation.
TESTS = [
    # ---------------------------------------------------------------- arithmetic
    ("arith-01", "arithmetic",
     "A store sells notebooks for $4 each. Priya buys 6 notebooks and a $7 pen, "
     "then pays with a $50 bill. How much change does she receive? "
     "Reply with only the number.", "19"),
    ("arith-02", "arithmetic",
     "A tank holds 480 liters. It is 25% full. How many more liters are needed to "
     "fill it completely? Reply with only the number.", "360"),
    ("arith-03", "arithmetic",
     "A worker earns $18/hour for the first 40 hours and $27/hour for overtime. "
     "She works 46 hours. What are her total earnings in dollars? "
     "Reply with only the number.", "882"),
    ("arith-04", "arithmetic",
     "If 5 machines make 5 widgets in 5 minutes, how many minutes do 100 machines "
     "need to make 100 widgets? Reply with only the number.", "5"),

    # ---------------------------------------------------------------- multi-hop
    ("hop-01", "multi-hop",
     "Anna is twice as old as Ben. Ben is 3 years older than Cara. Cara is 7. "
     "How old is Anna? Reply with only the number.", "20"),
    ("hop-02", "multi-hop",
     "A box has 3 red balls. Blue balls are double the red. Green balls are 5 fewer "
     "than blue. How many balls are there in total? Reply with only the number.", "10"),
    ("hop-03", "multi-hop",
     "Train A leaves at 9:00 traveling 60 km/h. It arrives when it has gone 180 km. "
     "A meeting starts 30 minutes after arrival. At what time does the meeting start? "
     "Reply in 24-hour HH:MM format only.", "12:30"),
    ("hop-04", "multi-hop",
     "A shop's revenue was $200 on Monday. Tuesday was 50% higher than Monday. "
     "Wednesday was $100 less than Tuesday. What was Wednesday's revenue? "
     "Reply with only the number.", "200"),

    # ---------------------------------------------------------------- temporal
    ("temp-01", "temporal",
     "A project starts on March 3 and lasts exactly 30 days, counting the start day "
     "as day 1. On what date does it end? Reply as 'Month Day' only, e.g. 'April 1'. "
     "Assume a non-leap year.", "April 1"),
    ("temp-02", "temporal",
     "If today is Wednesday, what day of the week is it 100 days from now? "
     "Reply with only the day name.", "Friday"),
    ("temp-03", "temporal",
     "A meeting runs from 14:45 to 17:20. How many minutes long is it? "
     "Reply with only the number.", "155"),
    ("temp-04", "temporal",
     "A flight departs 23:30 Monday and lasts 6 hours 45 minutes, arriving in the same "
     "time zone. What day does it arrive? Reply with only the day name.", "Tuesday"),

    # ---------------------------------------------------------------- logic
    ("logic-01", "logic",
     "All bloops are razzies. All razzies are lazzies. Are all bloops definitely "
     "lazzies? Reply with only Yes or No.", "Yes"),
    ("logic-02", "logic",
     "Some cats are black. All black things absorb heat. Does it follow that all cats "
     "absorb heat? Reply with only Yes or No.", "No"),
    ("logic-03", "logic",
     "If it rains, the ground gets wet. The ground is wet. Does it definitely follow "
     "that it rained? Reply with only Yes or No.", "No"),
    ("logic-04", "logic",
     "Three friends finish a race. Maya finished before Leo. Leo finished before Sam. "
     "Who finished last? Reply with only the name.", "Sam"),

    # -------------------------------------------------- instruction-following
    ("instr-01", "instruction-following",
     "Reply with exactly the word BANANA in all capital letters and nothing else.",
     "BANANA"),
    ("instr-02", "instruction-following",
     "What is 12 plus 30? Reply with only the number, no words, no punctuation.", "42"),
    ("instr-03", "instruction-following",
     "Name the capital of Japan. Reply with only the city name, no sentence.", "Tokyo"),
    ("instr-04", "instruction-following",
     "Count the letters in the word 'strawberry'. Reply with only the number.", "10"),

    # ---------------------------------------------------------------- adversarial
    # Each contains irrelevant or misleading detail the model must ignore.
    ("adv-01", "adversarial",
     "Marco has 8 apples. His friend Dana, who is 32 years old and owns 4 cars, gives "
     "him 5 more apples. How many apples does Marco have? Reply with only the number.",
     "13"),
    ("adv-02", "adversarial",
     "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. "
     "How much does the ball cost in cents? Reply with only the number.", "5"),
    ("adv-03", "adversarial",
     "A farmer had 17 sheep. All but 9 ran away. How many sheep does the farmer have "
     "left? Reply with only the number.", "9"),
    ("adv-04", "adversarial",
     "In a race you overtake the person in second place. What position are you in now? "
     "Reply with only the number.", "2"),
]

CATEGORIES = ["arithmetic", "multi-hop", "temporal", "logic",
              "instruction-following", "adversarial"]
