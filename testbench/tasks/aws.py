from farm.extensions import celery

@celery.task()
def add_together(a, b):
    print(a+b)
    return a + b
