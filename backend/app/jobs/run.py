import os
import sys
import logging
import importlib
from argparse import ArgumentParser
from sqlalchemy import text
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

def main():
    parser = ArgumentParser(description='Run background job')
    parser.add_argument('job_name', choices=['expire_viewings', 'retry_pdfs'])
    args = parser.parse_args()

    job_module = importlib.import_module(f'app.jobs.{args.job_name}')
    db = SessionLocal()
    try:
        result = job_module.run(db)
        db.commit()
        logger.info('Job %s completed', args.job_name, extra={'result': result})
        sys.exit(0)
    except Exception as exc:
        db.rollback()
        logger.exception('Job %s failed', args.job_name)
        sys.exit(1)

if __name__ == '__main__':
    # Scheduler integration
    if os.getenv('RUN_SCHEDULER') == 'true':
        from apscheduler.schedulers.blocking import BlockingScheduler
        scheduler = BlockingScheduler()
        scheduler.add_job(lambda: run_job('expire_viewings'), 'interval', hours=1, id='expire_viewings')
        scheduler.add_job(lambda: run_job('retry_pdfs'), 'interval', minutes=15, id='retry_pdfs')
        logger.info('Starting APScheduler')
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info('Scheduler stopped')
    else:
        main()

def run_job(job_name: str):
    """Helper to run a job for the scheduler, logs outcome."""
    try:
        module = importlib.import_module(f'app.jobs.{job_name}')
        db = SessionLocal()
        result = module.run(db)
        db.commit()
        logger.info('Scheduled job %s succeeded', job_name, extra={'result': result})
    except Exception:
        logger.exception('Scheduled job %s failed', job_name)
        # Scheduler will continue next run
