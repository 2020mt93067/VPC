"""
Step file for feature testing
"""
from behave import given, when, then
import json
from CreateVPC.app import app as flask_app


@given('the method "{variable}" exists')
def step_impl(context, variable):
    context.var = variable
    context.app = flask_app.test_client()
    context.headers = {'content-type': 'application/json'}
    context.body = {}


@given('input variable "{var}" is "{value}"')
def step_impl(context, var, value):
    context.body[var] = value


@given('input variable "region" is ""')
def step_impl(context):
    context.body["region"] = ""


@when('url "{url}" is called')
def step_impl(context, url):
    context.url = url
    print(json.dumps(context.body))
    context.response = context.app.post(context.url, data=json.dumps(context.body), headers=context.headers)


@then('we should get response 200')
def step_impl(context):
    assert context.response.status_code == 200


@then('we should get response 400')
def step_impl(context):
    assert context.response.status_code == 400


@then('we should get response 500')
def step_impl(context):
    assert context.response.status_code == 500
