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


        stage("dependances check") {
            steps {
                sh 'python3 -m venv .venv'
                sh '.venv/bin/pip install --upgrade pip'
                sh '.venv/bin/pip install -r requirements.txt'
            }
        }
    }
}