node {
  withCredentials([string(credentialsId: 'boundlessgeoadmin-token', variable: 'GITHUB_TOKEN'), string(credentialsId: 'sonar-jenkins-pipeline-token', variable: 'SONAR_TOKEN')]) {

    currentBuild.result = "SUCCESS"

    try {
      stage('Checkout'){
        checkout scm
        sh """
          git submodule update --init
          echo "Running ${env.BUILD_ID} on ${env.JENKINS_URL}"
        """
        checkout([$class: 'GitSCM',
                  branches: [[name: '*/master']],
                  doGenerateSubmoduleConfigurations: false,
                  extensions: [[$class: 'RelativeTargetDirectory',
                                relativeTargetDir: './vendor/exchange-mobile-extension']],
                  submoduleCfg: [],
                  userRemoteConfigs: [[credentialsId: 'BoundlessAdminGitHub',
                                       url: 'https://github.com/boundlessgeo/exchange-mobile-extension.git']]])
        sh """
          # https://issues.jenkins-ci.org/browse/JENKINS-44909
          rm -r vendor/exchange-mobile-extension@tmp
        """
      }

      stage('Setup'){
        sh """
          docker pull 'quay.io/boundlessgeo/sonar-maven-py3-alpine'
          docker-compose down
          docker system prune -f
        """
      }

      stage('Style Checks'){
        parallel (
            "pycodestyle" : {
              bashDocker(
                'quay.io/boundlessgeo/sonar-maven-py3-alpine',
                'pycodestyle exchange --ignore=E722,E731'
              )
            },
            "yamllint" : {
              bashDocker(
                'quay.io/boundlessgeo/sonar-maven-py3-alpine',
                'yamllint -d "{extends: relaxed, rules: {line-length: {max: 120}}}" $(find . -name "*.yml" -not -path "./vendor/*")'
              )
            },
            "flake8" : {
              bashDocker(
                'quay.io/boundlessgeo/sonar-maven-py3-alpine',
                'flake8 --ignore=F405,E722,E731 exchange'
              )
            }
        )
      }

      stage('Build'){
        parallel (
          "maploom" : {
            bashDocker(
              'quay.io/boundlessgeo/bex-nodejs-bower-grunt',
              '. docker/devops/helper.sh && build-maploom'
            )
          },
          "bex" : {
            sh """
              docker rm -f \$(docker ps -aq) || echo "no containers to remove"
              docker-compose up --build --force-recreate -d
            """
            timeout(time: 10, unit: 'MINUTES')  {
              waitUntil {
                script {
                  def r = sh script: 'wget -q http://localhost -O /dev/null', returnStatus: true
                  return (r == 0);
                }
              }
            }
            sh """
              docker-compose logs
            """
          }
        )
      }

      stage('Verify Migrations'){
        sh """
          docker-compose exec -T exchange /bin/bash -c '. docker/devops/helper.sh && makemigrations-check'
        """
      }

      stage('py.test'){
        sh """
          docker-compose exec -T exchange /bin/bash -c '/code/docker/exchange/run_tests.sh'
        """
      }

      if (env.BRANCH_NAME == 'master') {
        stage('SonarQube Analysis') {
          sh """
            docker run -e SONAR_HOST_URL='https://sonar-ciapi.boundlessgeo.io' \
                       -e SONAR_TOKEN=$SONAR_TOKEN \
                       -v \$(pwd -P):/code \
                       -w /code quay.io/boundlessgeo/sonar-maven-py3-alpine bash \
                       -c '. docker/devops/helper.sh && sonar-scan'
            """
        }
      }

    }
    catch (err) {

      currentBuild.result = "FAILURE"
        throw err
    } finally {
      // Success or failure, always send notifications
      echo currentBuild.result
      sh """
        docker-compose down
        docker system prune -f
        """
      notifyBuild(currentBuild.result)
    }

  }
}


// Slack Integration
def notifyBuild(String buildStatus = currentBuild.result) {

  // generate a custom url to use the blue ocean endpoint
  def jobName =  "${env.JOB_NAME}".split('/')
  def repo = jobName[0]
  def pipelineUrl = "${env.JENKINS_URL}blue/organizations/jenkins/${repo}/detail/${env.BRANCH_NAME}/${env.BUILD_NUMBER}/pipeline"
  // Default values
  def colorName = 'RED'
  def colorCode = '#FF0000'
  def subject = "${buildStatus}\nJob: ${env.JOB_NAME}\nBuild: ${env.BUILD_NUMBER}\nJenkins: ${pipelineUrl}\n"
  def summary = (env.CHANGE_ID != null) ? "${subject}\nAuthor: ${env.CHANGE_AUTHOR}\n${env.CHANGE_URL}\n" : "${subject}"

  // Override default values based on build status
  if (buildStatus == 'SUCCESS') {
    colorName = 'GREEN'
    colorCode = '#228B22'
  }

  // Send notifications
  slackSend (color: colorCode, message: summary, channel: '#exchange-bots')
}
