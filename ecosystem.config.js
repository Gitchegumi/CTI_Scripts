module.exports = {
  apps: [{
    name: 'tradegumi',
    cwd: '/home/dockegumi/.openclaw/workspace/repos/CTI_Scripts',
    script: './tradegumi-start.sh',
    interpreter: '/bin/bash',
    watch: false,
    autorestart: true,
    max_restarts: 10,
    min_uptime: '30s',
    env: {
      PYTHONUNBUFFERED: '1'
    },
    log_file: '/home/dockegumi/.openclaw/workspace/repos/CTI_Scripts/logs/tradegumi-pm2.log',
    out_file: '/home/dockegumi/.openclaw/workspace/repos/CTI_Scripts/logs/tradegumi-out.log',
    error_file: '/home/dockegumi/.openclaw/workspace/repos/CTI_Scripts/logs/tradegumi-error.log',
    time: true,
    restart_delay: 5000
  }]
};
