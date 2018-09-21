// JOB_BASE_NAME is not reliably available in Multibranch Pipeline
def CLIENT_PREFIX = "copy-s3-uploads"
pipeline {
    agent any
    options {
        disableConcurrentBuilds()
    }
    environment {
        CLIENT_PREFIX     = "copy-s3-uploads"
        ACTOR_ID_PROD     = 'MPAXmvZGABzN'
        ACTOR_ID_STAGING  = 'MPAXmvZGABzN'
        ACTOR_WORKERS = 6
        PYTEST_OPTS       = '-s -vvv'
        ABACO_DEPLOY_OPTS = ''
        AGAVE_CACHE_DIR   = "${HOME}/credentials_cache/${CLIENT_PREFIX}"
        AGAVE_JSON_PARSER = "jq"
        AGAVE_TENANTID    = "sd2e"
        AGAVE_APISERVER   = "https://api.sd2e.org"
        AGAVE_USERNAME    = credentials('sd2etest-tacc-username')
        AGAVE_PASSWORD    = credentials('sd2etest-tacc-password')
        REGISTRY_USERNAME = "sd2etest"
        REGISTRY_PASSWORD = credentials('sd2etest-dockerhub-password')
        REGISTRY_ORG      = credentials('sd2etest-dockerhub-org')
        PATH = "${HOME}/bin:${HOME}/sd2e-cloud-cli/bin:${env.PATH}"
        SECRETS_FILE = credentials('data-catalog-secrets-json-prod')
        SECRETS_FILE_STAGING = credentials('data-catalog-secrets-json-prod')
        CI                = "true"
        }
    stages {
        stage('Build project') {
            steps {
                println("Building against branch ${BRANCH_NAME}")
                sh "get-job-client ${CLIENT_PREFIX}-${BRANCH_NAME} ${BUILD_ID}"
                sh "cat ${SECRETS_FILE} > secrets.json"
                sh "make clean || true"
                sh "make image"
            }
        }
        stage('Run integration tests') {
            steps {
                sh "NOCLEANUP=1 make tests-integration"
                sh "FORCE_LOCK_RELEASE=1 release-job-client ${CLIENT_PREFIX}-${BRANCH_NAME} ${BUILD_ID}"
            }
        }
        stage('Deploy to staging from develop') {
            when {
                branch 'develop'
            }
            environment {
                AGAVE_USERNAME    = 'sd2eadm'
                AGAVE_PASSWORD    = credentials('sd2eadm-password')
            }
            steps {
                script {
                    sh "get-job-client ${CLIENT_PREFIX}-${BRANCH_NAME}-deploy ${BUILD_ID}"
                    reactorName = sh(script: 'cat reactor.rc | egrep -e "^REACTOR_NAME=" | sed "s/REACTOR_NAME=//"', returnStdout: true).trim()
                    sh(script: "make deploy ACTOR_ID=${ACTOR_ID_STAGING}", returnStdout: false)
                    // TODO - update alias
                    println("Deployed ${reactorName}:staging with actorId ${ACTOR_ID_STAGING}")
                    slackSend ":tacc: Deployed *${reactorName}:staging* with actorId *${ACTOR_ID_STAGING}*"
                }
            }
        }
        stage('Deploy to production from master') {
            when {
                branch 'master'
            }
            environment {
                AGAVE_USERNAME    = 'sd2eadm'
                AGAVE_PASSWORD    = credentials('sd2eadm-password')
            }
            steps {
                script {
                    sh "get-job-client ${CLIENT_PREFIX}-${BRANCH_NAME}-deploy ${BUILD_ID}"
                    reactorName = sh(script: 'cat reactor.rc | egrep -e "^REACTOR_NAME=" | sed "s/REACTOR_NAME=//"', returnStdout: true).trim()
                    // TODO - update alias
                    sh(script: "make deploy ACTOR_ID=${ACTOR_ID_PROD}", returnStdout: false)
                    println("Deployed ${reactorName}:production with actorId ${ACTOR_ID_PROD}")
                    slackSend ":tacc: Deployed *${reactorName}:prod* with actorId *${ACTOR_ID_PROD}*"
                }
            }
        }
    }
    post {
        always {
            sh "FORCE_LOCK_RELEASE=1 release-job-client ${CLIENT_PREFIX}-${BRANCH_NAME} ${BUILD_ID}"
            sh "FORCE_LOCK_RELEASE=1 release-job-client ${CLIENT_PREFIX}-${BRANCH_NAME}-deploy ${BUILD_ID}"
            archiveArtifacts artifacts: 'input, output, create_mapped_name_failures.csv', fingerprint: true, excludes: 'secrets.json', allowEmptyArchive: true
            deleteDir()
        }
        success {
            slackSend ":white_check_mark: *${env.JOB_NAME}/${env.BUILD_NUMBER}* completed"
            emailext (
                    subject: "${env.JOB_NAME}/${env.BUILD_NUMBER} completed",
                    body: """<p>Build: ${env.BUILD_URL}</p>""",
                    recipientProviders: [[$class: 'DevelopersRecipientProvider']],
                    replyTo: "jenkins@sd2e.org",
                    from: "jenkins@sd2e.org"
            )
        }
        failure {
            slackSend ":bomb: *${env.JOB_NAME}/${env.BUILD_NUMBER}* failed"
            emailext (
                    subject: "${env.JOB_NAME}/${env.BUILD_NUMBER} failed",
                    body: """<p>Build: ${env.BUILD_URL}</p>""",
                    recipientProviders: [[$class: 'DevelopersRecipientProvider']],
                    replyTo: "jenkins@sd2e.org",
                    from: "jenkins@sd2e.org"
            )
        }
    }
}
