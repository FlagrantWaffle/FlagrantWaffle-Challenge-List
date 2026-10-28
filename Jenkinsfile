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
    }
}