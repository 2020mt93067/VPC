from flask import Flask
from cloudx_vpc_service.app import app

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5001)