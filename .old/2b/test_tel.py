from core.telemetry import telemetry
import time

print("Logging test event...")
telemetry.log("test_session", "test_event", {"message": "hello world"})
print("Exporting to markdown...")
telemetry.export_to_markdown("test_session")
print("Done.")
