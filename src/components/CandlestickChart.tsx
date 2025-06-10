const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: false
    },
    tooltip: {
      mode: 'index' as const,
      intersect: false,
      backgroundColor: 'rgba(30, 41, 59, 0.95)',
      titleColor: '#94a3b8',
      bodyColor: '#ffffff',
      borderColor: '#4ade80',
      borderWidth: 1,
      callbacks: {
        label: (context: any) => `$${context.parsed.y.toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2
        })}`
      }
    }
  },
  scales: {
    x: {
      display: true,
      grid: {
        color: 'rgba(255, 255, 255, 0.1)',
        drawBorder: false
      },
      ticks: {
        color: '#94a3b8',
        maxTicksLimit: 6,
        maxRotation: 0,
        minRotation: 0
      },
      border: {
        display: false
      }
    },
    y: {
      display: true,
      position: 'right' as const,
      grid: {
        color: 'rgba(255, 255, 255, 0.1)',
        drawBorder: false
      },
      ticks: {
        color: '#94a3b8',
        maxTicksLimit: 8,
        callback: (value: any) => `$${value.toLocaleString()}`,
        padding: 10
      },
      border: {
        display: false
      },
      beginAtZero: false,
      grace: '5%'
    }
  },
  interaction: {
    intersect: false,
    mode: 'index' as const
  },
  animation: {
    duration: 300
  },
  elements: {
    point: {
      hoverRadius: 8
    }
  }
}; 