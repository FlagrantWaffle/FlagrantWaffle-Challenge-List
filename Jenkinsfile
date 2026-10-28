pipeline {
    agent any

    stages {
        stage("confirm") {
            steps {
                sh 'echo "checked out successfully"'
                sh 'ls -la'
            }
        }

        stage("python compile check") {
            steps {
                sh 'python3 -m compileall -q .'
            }
        }

        stage("dependancies check") {
            steps {
                sh 'python3 -m venv .venv'
                sh '.venv/bin/pip install --upgrade pip'
                sh '.venv/bin/pip install -r requirements.txt'
            }
        }

        stage("unit tests") {
            steps {
                sh ".venv/bin/python -m pytest -v"
            }
        }


        stage("docker build") {
            steps {
                sh 'docker build -t fwcl-ci:$BUILD_NUMBER .'
            }
        }
        

        stage("endpoint tests") {
            steps {
                sh '.venv/bin/python -m pytest -v tests/test_endpoints.py'
            }
        }


    }


    post {
        always {
            sh 'docker image rm -f fwcl-ci:$BUILD_NUMBER || true'
        }
    }
}