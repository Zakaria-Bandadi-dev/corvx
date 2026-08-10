from flask import jsonify
from app import app
from config.countries import COUNTRIES
from robots.news_robot import robot_status, run_robot

def robot_status_json():
    data = dict(robot_status)
    data["last_run_start"] = robot_status["last_run_start"].isoformat() if robot_status["last_run_start"] else None
    data["last_run_end"] = robot_status["last_run_end"].isoformat() if robot_status["last_run_end"] else None
    if robot_status["current_country"] in COUNTRIES:
        data["current_country_name"] = COUNTRIES[robot_status["current_country"]]["name"]
    else:
        data["current_country_name"] = None
    return jsonify(data)


def manual_robot():
    run_robot()
    return """
    <h2>Robot finished.</h2>
    <a href="/">Back to website</a>
    """

