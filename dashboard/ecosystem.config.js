module.exports = {
  apps: [{
    name: 'tradegumi-dashboard',
    cwd: '/home/dockegumi/.openclaw/workspace/repos/CTI_Scripts/dashboard',
    script: 'npm',
    args: 'start -- -p 3002',
    autorestart: true,
    max_restarts: 10,
    min_uptime: '10s',
    env: {
      NODE_ENV: 'production',
      PORT: 3002
    },
    log_file: '/home/dockegumi/.openclaw/workspace/repos/CTI_Scripts/logs/dashboard-pm2.log',
    out_file: '/home/dockegumi/.openclaw/workspace/repos/CTI_Scripts/logs/dashboard-out.log',
    error_file: '/home/dockegumi/.openclaw/workspace/repos/CTI_Scripts/logs/dashboard-error.log',
    time: true
  }]
};
