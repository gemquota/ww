import unittest
from rab.planner import plan_goal

class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {"capabilities": [
            {"id":"android.notification","state":"unavailable"},
            {"id":"android.macrodroid_app","state":"verified"},
            {"id":"automation.macrodroid_builder","state":"executable"},
            {"id":"android.screenshot","state":"unavailable"},
            {"id":"automation.rab_android_bridge","state":"awaiting_setup"}
        ]}

    def test_notification_intent_wins_over_status_word(self):
        plan = plan_goal("Create an Android notification with RAB status", self.manifest)
        self.assertEqual(plan["status"], "awaiting_setup")
        self.assertEqual(plan["steps"][0]["kind"], "connect")

    def test_status_intent(self):
        self.assertEqual(plan_goal("Show RAB status", self.manifest)["status"], "ready")

    def test_screen_actions_route_to_single_bridge(self):
        for goal, tool in [("take a screenshot","rab_screenshot"),("tap at 100,200","rab_tap"),
                           ("drag across the screen","rab_drag"),("type hello","rab_type")]:
            plan=plan_goal(goal,self.manifest)
            self.assertEqual(plan["status"],"awaiting_setup")
            self.assertEqual(plan["steps"][0]["tool_name"],tool)

    def test_unknown_goal_is_not_guessed(self):
        self.assertEqual(plan_goal("Make the phone do something clever", self.manifest)["status"], "unmapped")

if __name__ == "__main__":
    unittest.main()
