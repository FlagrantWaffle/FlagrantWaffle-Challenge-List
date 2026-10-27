pipeline {
    agent any

    stages {
        stage('checkout') {
            steps {
                checkout scm
            }
        }

        stage("confirm") {
            steps {
                sh 'echo "checked out successfully"'
                sh 'ls-la'
            }
        }
    }
}