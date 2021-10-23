import http
from jsonschema import ValidationError
from CreateVPC.app import app
from CreateVPC.app.models.create_vpc import main, validate_input_json
from flask import request, jsonify, make_response


@app.route("/create/vpc1", methods=['POST'])
def calling_create_vpc(**kwargs):
    """
    calling main method to create VPC
    :param kwargs:
    :return: dict
    """
    try:
        requests = request.get_json()
        validate_input_json("vpc_schema_validation.json", requests)
        return jsonify(main(requests))
    except ValidationError as e:
        return make_response(jsonify({"ValidationError": "Input json is not valid"}), http.HTTPStatus.BAD_REQUEST)
