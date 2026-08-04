import os

# Keep tests isolated from machine-level DEBUG/APP_ENV variables.
os.environ["APP_ENV"] = "test"
os.environ["DEBUG"] = "true"
