import requests                                  # requests: για HTTP αιτήματα προς το RAG backend
from rasa_sdk import Action, Tracker             # Βασικές κλάσεις του Rasa SDK για custom actions
from rasa_sdk.executor import CollectingDispatcher# Βασικές κλάσεις του Rasa SDK για custom actions
from rasa_sdk.events import SlotSet, FollowupAction  # Events του Rasa για διαχείριση κατάστασης (slots, follow-up actions)
import uuid                             # uuid: για δημιουργία μοναδικών αναγνωριστικών (π.χ., quiz_id) 

class ActionRAGAnswer(Action):          # ACTION 1: Κανονική απάντηση από RAG (normal mode)
    def name(self):                     # Όνομα action (όπως δηλώνεται στο domain.yml)
        return "action_rag_answer"

    def run(self, dispatcher, tracker, domain):
        question = tracker.latest_message.get("text")         # Παίρνουμε το τελευταίο μήνυμα του χρήστη (ερώτηση)
        response = requests.post(                       # Στέλνουμε την ερώτηση στο RAG backend (normal mode)
            "http://rag:8000/ask?mode=normal",          #Στέλνουμε json με την ερώτηση στο RAG 
            json={"question": question}
        )
        # Παίρνουμε την απάντηση από το JSON
        # Αν δεν υπάρχει, δίνουμε default μήνυμα
        answer = response.json().get("answer", "Δεν μπόρεσα να δώσω απάντηση.")

        dispatcher.utter_message(text=answer)         # Στέλνουμε την απάντηση στον χρήστη
        return [SlotSet("previous_answer", answer)]   # Αποθηκεύουμε την απάντηση στο slot "previous_answer"


class ActionRAGAnswerSimple(Action):        # ACTION 2: Απλούστευση προηγούμενης απάντησης (simple mode)
    def name(self):                     # Όνομα action (όπως δηλώνεται στο domain.yml)
        return "action_rag_answer_simple"     

    def run(self, dispatcher, tracker, domain):           

        #Παίρνουμε την προηγούμενη απάντηση από το slot
        previous = tracker.get_slot("previous_answer")

        #Αν δεν υπάρχει, απλά λέμε κάτι φιλικό
        if not previous:
            dispatcher.utter_message("Δεν έχω κάποια προηγούμενη απάντηση για να την κάνω πιο απλή.")
            return []

        #Στέλνουμε την προηγούμενη απάντηση στο RAG simple endpoint
        response = requests.post(
            "http://rag:8000/ask?mode=simple",     
            json={"text": previous},                # Στέλνουμε την προηγούμενη απάντηση για απλούστευση
            timeout=120                      # Χρονικό όριο 120 δευτερολέπτων
        )

        #Παίρνουμε την απλουστευμένη απάντηση
        answer = response.json().get("answer", "Δεν μπόρεσα να απλοποιήσω την απάντηση.")

        #Τη στέλνουμε στον μαθητή (δεν αποθηκεύουμε στο slot!)
        dispatcher.utter_message(text=answer)
        return []


class ActionGetExercise(Action):       # ACTION 3: Λήψη άσκησης από RAG για κουίζ
    def name(self):
        return "action_get_exercise"   # Όνομα action (όπως δηλώνεται στο domain.yml)

    def run(self, dispatcher, tracker, domain): # Κύρια μέθοδος εκτέλεσης του action

        topic = tracker.get_slot("exercise_topic") or tracker.latest_message.get("text") # Παίρνουμε το θέμα της άσκησης από το slot ή από το τελευταίο μήνυμα
        difficulty = tracker.get_slot("exercise_difficulty") or "easy"  # Παίρνουμε τη δυσκολία της άσκησης από το slot ή ορίζουμε ως "easy" αν δεν υπάρχει 
        index = tracker.get_slot("exercise_index") or 0  # Παίρνουμε το index της άσκησης από το slot ή ορίζουμε ως 0 αν δεν υπάρχει
        quiz_id = tracker.get_slot("quiz_id") or str(uuid.uuid4())          # Παίρνουμε ή δημιουργούμε ένα μοναδικό quiz_id
        questions_count = tracker.get_slot("questions_count") or 0  # Παίρνουμε τον αριθμό των ερωτήσεων που έχουν απαντηθεί

        #  Σταματάμε στις 5 ερωτήσεις
        if questions_count >= 5: 
            dispatcher.utter_message("Τέλος κουίζ! Συγχαρητήρια, απάντησες σε 5 ερωτήσεις! Τελικό σκορ: {}/5".format(tracker.get_slot("score") or 0))
            return [                        # Επαναφορά όλων των σχετικών slots
                SlotSet("quiz_id", None),   # Ακύρωση του quiz_id
                SlotSet("questions_count", 0), # Επαναφορά του μετρητή ερωτήσεων
                SlotSet("exercise_index", 0),  # Επαναφορά του index άσκησης
                SlotSet("exercise_difficulty", "easy"),  # Επαναφορά της δυσκολίας σε "easy"
                SlotSet("exercise_topic", None),   # Ακύρωση του θέματος άσκησης
                SlotSet("exercise_text", None),   # Ακύρωση του κειμένου άσκησης
                SlotSet("exercise_solution", None),   # Ακύρωση της λύσης άσκησης
                SlotSet("exercise_explanation", None),   # Ακύρωση της εξήγησης άσκησης
                SlotSet("score", 0),            # Επαναφορά του σκορ
            ]
        rag_query = f"Άσκηση από {topic}, δυσκολία {difficulty}" # Δημιουργία ερωτήματος για το RAG
        response = requests.post(                    
            "http://rag:8000/ask?mode=exercises",   #Στέλνει το ερώτημα στο RAG
            json={
                "question": rag_query,            
                "index": index,
                "difficulty": difficulty,
                "quiz_id": quiz_id
            },
            timeout=120
        ).json()

        question = response.get("question")   # Παίρνουμε την άσκηση από την απάντηση  
        solution = response.get("solution")  # Παίρνουμε τη λύση της άσκησης
        explanation = response.get("explanation")   # Παίρνουμε την εξήγηση της άσκησης


        # Αν το RAG δεν έχει άλλη άσκηση, σταματάμε το κουίζ
        if not question or solution is None:        
            dispatcher.utter_message("Δεν βρέθηκε άλλη άσκηση από το RAG για αυτό το θέμα/επίπεδο.")
            return [
                SlotSet("quiz_id", None),  # Ακύρωση του quiz_id
                SlotSet("questions_count", 0),  # Επαναφορά του μετρητή ερωτήσεων
                SlotSet("exercise_index", 0),   # Επαναφορά του index άσκησης
                SlotSet("exercise_difficulty", "easy"),  # Επαναφορά της δυσκολίας σε "easy"
                SlotSet("exercise_topic", None),    # Ακύρωση του θέματος άσκησης
                SlotSet("exercise_text", None),     # Ακύρωση του κειμένου άσκησης
                SlotSet("exercise_solution", None),  # Ακύρωση της λύσης άσκησης
                SlotSet("exercise_explanation", None),  # Ακύρωση της εξήγησης άσκησης
                SlotSet("score", 0),          # Επαναφορά του σκορ
            ]

        dispatcher.utter_message(text=question)  # Στέλνουμε την άσκηση στον χρήστη

        #   εδώ αυξάνεται το index & ο μετρητής ερωτήσεων
        return [
            SlotSet("quiz_id", quiz_id),    # Διατήρηση του quiz_id
            SlotSet("exercise_topic", topic),  # Διατήρηση του θέματος άσκησης
            SlotSet("exercise_difficulty", difficulty), # Διατήρηση της δυσκολίας άσκησης
            SlotSet("exercise_text", question),# Αποθήκευση του κειμένου της άσκησης
            SlotSet("exercise_solution", solution),# Αποθήκευση της λύσης της άσκησης
            SlotSet("exercise_index", index + 1),  # Αύξηση του index για την επόμενη άσκηση
            SlotSet("questions_count", questions_count + 1),  # Αύξηση του μετρητή ερωτήσεων
            SlotSet("exercise_explanation", explanation),   # Αποθήκευση της εξήγησης της άσκησης
        ]


class ActionCheckExerciseAnswer(Action):    # ACTION 4: Έλεγχος απάντησης άσκησης κουίζ
    def name(self):                             # Όνομα action (όπως δηλώνεται στο domain.yml)
        return "action_check_exercise_answer"   # Κύρια μέθοδος εκτέλεσης του action

    def run(self, dispatcher, tracker, domain):  # Κύρια μέθοδος εκτέλεσης του action
        user_answer = (tracker.latest_message.get("text") or "").strip().lower()   # Παίρνουμε την απάντηση του χρήστη και την κανονικοποιούμε
        correct_answer = tracker.get_slot("exercise_solution")  # Παίρνουμε τη σωστή απάντηση από το slot
        difficulty = tracker.get_slot("exercise_difficulty") or "easy"  # Παίρνουμε τη δυσκολία της άσκησης από το slot ή ορίζουμε ως "easy" αν δεν υπάρχει

        if correct_answer is None:                  # Αν δεν υπάρχει σωστή απάντηση, σημαίνει ότι δεν υπάρχει ενεργή άσκηση
            dispatcher.utter_message("Δεν υπάρχει ενεργή άσκηση.") 
            return []   # Επιστρέφουμε χωρίς να κάνουμε τίποτα

        correct = str(correct_answer).strip().lower()   # Κανονικοποιούμε τη σωστή απάντηση για σύγκριση

        # ================== ΣΩΣΤΗ ==================
        if user_answer == correct:                  # Αν η απάντηση του χρήστη είναι σωστή
            score = tracker.get_slot("score") or 0  # Παίρνουμε το τρέχον σκορ από το slot ή ορίζουμε ως 0 αν δεν υπάρχει
            score += 1                          # Αυξάνουμε το σκορ κατά 1

            dispatcher.utter_message(f"Απάντησες σωστά!  Σκορ: {score}")   # Ενημερώνουμε τον χρήστη για το σωστό
            next_level = {"easy": "medium", "medium": "hard", "hard": "hard"}[difficulty]   # Προχωράμε στο επόμενο επίπεδο δυσκολίας

            events = [                          # Ενημερώνουμε τα σχετικά slots
                SlotSet("score", score),        # Ενημέρωση του σκορ
                SlotSet("exercise_solution", None),# Ακύρωση της λύσης άσκησης
                SlotSet("exercise_text", None),     # Ακύρωση του κειμένου άσκησης
                SlotSet("exercise_explanation", None),  # Ακύρωση της εξήγησης άσκησης
            ]

            if next_level != difficulty:        # Αν αλλάζει το επίπεδο δυσκολίας, ενημερώνουμε το slot
                events.append(SlotSet("exercise_difficulty", next_level))  # Ενημέρωση της δυσκολίας άσκησης
                events.append(SlotSet("exercise_index", 0))             # Επαναφορά του index άσκησης για το νέο επίπεδο

            events.append(FollowupAction("action_get_exercise"))    # Προσθήκη follow-up action για λήψη νέας άσκησης
            return events                                   # Επιστρέφουμε τα events για ενημέρωση της κατάστασης


        # ================== ΛΑΘΟΣ ==================
        explanation = tracker.get_slot("exercise_explanation")   # Παίρνουμε την εξήγηση της άσκησης από το slot

        if explanation:                     # Αν υπάρχει εξήγηση, την προσθέτουμε στο μήνυμα    
            dispatcher.utter_message(f" Λάθος.\n"f" Σωστή απάντηση: {correct}\n"f" Εξήγηση: {explanation}")
        else:               # Αν δεν υπάρχει εξήγηση, απλά δείχνουμε τη σωστή απάντηση  
            dispatcher.utter_message(f" Λάθος. Σωστή απάντηση: {correct}")
            

        return [                            # Επαναφορά των σχετικών slots και λήψη νέας άσκησης
            SlotSet("exercise_solution", None),# Ακύρωση της λύσης άσκησης
            SlotSet("exercise_text", None), # Ακύρωση του κειμένου άσκησης
            SlotSet("exercise_explanation", None),  # Ακύρωση της εξήγησης άσκησης
            FollowupAction("action_get_exercise")  # Προσθήκη follow-up action για λήψη νέας άσκησης
        ]

