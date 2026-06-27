pipeline {
    agent any

    parameters {
        choice(
            name: 'APP_ACTION',
            choices: ['status', 'start', 'stop', 'restart', 'redeploy', 'logs', 'health'],
            description: 'YouTube Downloader 제어 액션을 선택하세요.'
        )
    }

    environment {
        REMOTE_HOST = '192.168.0.36'
        REMOTE_USER = 'chahero'
        SSH_CREDENTIAL_ID = 'mac-ssh-key'
        PROJECT_DIR = '/Users/chahero/git-repository/youtube-downloader'

        HOMEBREW_BIN = '/opt/homebrew/bin'
        PYTHON_BIN = '/opt/homebrew/bin/python3'
    }

    stages {
        stage('YouTube Downloader Management') {
            steps {
                sshagent([SSH_CREDENTIAL_ID]) {
                    script {
                        def sshCmd = "ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=publickey -o PasswordAuthentication=no ${REMOTE_USER}@${REMOTE_HOST}"
                        def remotePrefix = "export PATH=${HOMEBREW_BIN}:\\$PATH; export PYTHON_BIN=${PYTHON_BIN}; cd ${PROJECT_DIR}"

                        sh "${sshCmd} '${remotePrefix} && bash ./manage.sh ${params.APP_ACTION}'"
                    }
                }
            }
        }
    }
}
