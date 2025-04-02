from flask import Flask, render_template, request, jsonify, redirect, url_for
import redis
import json
import os
import time
from datetime import datetime

app = Flask(__name__)

# Connect to Redis
redis_client = redis.Redis(host=os.environ.get('REDIS_HOST', 'localhost'), port=6379, db=0)

@app.route('/')
def index():
    """Dashboard home page"""
    return render_template('index.html')

@app.route('/accounts')
def accounts():
    """Account management page"""
    # Load accounts from file
    accounts_data = []
    try:
        with open('/app/data/accounts.json', 'r') as f:
            accounts_data = json.load(f)
    except:
        pass
    
    return render_template('accounts.html', accounts=accounts_data)

@app.route('/proxies')
def proxies():
    """Proxy management page"""
    # Load proxies from file
    proxies_data = []
    try:
        with open('/app/data/proxies.json', 'r') as f:
            proxies_data = json.load(f)
    except:
        pass
    
    # Get proxy stats
    proxy_stats = {}
    try:
        proxy_stats_json = redis_client.get('proxy_stats')
        if proxy_stats_json:
            proxy_stats = json.loads(proxy_stats_json)
    except:
        pass
    
    return render_template('proxies.html', proxies=proxies_data, stats=proxy_stats)

@app.route('/tasks')
def tasks():
    """Task management and monitoring page"""
    # Get queue stats
    task_count = redis_client.llen('task_queue')
    result_count = redis_client.llen('result_queue')
    
    # Get recent results
    results = []
    try:
        result_data = redis_client.lrange('result_queue', 0, 19)  # Get up to 20 recent results
        for result_json in result_data:
            results.append(json.loads(result_json))
    except:
        pass
    
    return render_template('tasks.html', task_count=task_count, result_count=result_count, results=results)

@app.route('/api/accounts', methods=['GET'])
def api_accounts():
    """API endpoint for accounts data"""
    try:
        with open('/app/data/accounts.json', 'r') as f:
            accounts_data = json.load(f)
        return jsonify(accounts_data)
    except:
        return jsonify([])

@app.route('/api/proxies', methods=['GET'])
def api_proxies():
    """API endpoint for proxies data"""
    try:
        with open('/app/data/proxies.json', 'r') as f:
            proxies_data = json.load(f)
        return jsonify(proxies_data)
    except:
        return jsonify([])

@app.route('/api/tasks', methods=['GET'])
def api_tasks():
    """API endpoint for task queue data"""
    task_count = redis_client.llen('task_queue')
    result_count = redis_client.llen('result_queue')
    
    return jsonify({
        'task_count': task_count,
        'result_count': result_count,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/create_accounts', methods=['POST'])
def api_create_accounts():
    """API endpoint to create accounts"""
    try:
        count = int(request.form.get('count', 1))
        domain = request.form.get('domain', 'gmail.com')
        use_proxy = request.form.get('use_proxy', 'true').lower() == 'true'
        
        for i in range(count):
            task_data = {
                'task_id': f"ui-{int(time.time())}-{i}",
                'type': 'create_account',
                'timestamp': datetime.now().isoformat(),
                'email_domain': domain,
                'use_proxy': use_proxy
            }
            redis_client.rpush('task_queue', json.dumps(task_data))
        
        return jsonify({
            'success': True,
            'message': f"Queued {count} account creation tasks",
            'count': count
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"Error: {str(e)}"
        }), 400

@app.route('/api/register_platforms', methods=['POST'])
def api_register_platforms():
    """API endpoint to register accounts on platforms"""
    try:
        email = request.form.get('email')
        platforms = request.form.get('platforms', 'twitter,telegram').split(',')
        
        if not email:
            # Register all accounts
            try:
                with open('/app/data/accounts.json', 'r') as f:
                    accounts_data = json.load(f)
                    
                for account in accounts_data:
                    for platform in platforms:
                        task_data = {
                            'task_id': f"ui-{int(time.time())}-{account['email']}-{platform}",
                            'type': 'register_platform',
                            'timestamp': datetime.now().isoformat(),
                            'email': account['email'],
                            'platform': platform.strip()
                        }
                        redis_client.rpush('task_queue', json.dumps(task_data))
                        
                return jsonify({
                    'success': True,
                    'message': f"Queued registration tasks for {len(accounts_data)} accounts on {len(platforms)} platforms",
                    'count': len(accounts_data) * len(platforms)
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f"Error registering all accounts: {str(e)}"
                }), 400
        else:
            # Register specific account
            for platform in platforms:
                task_data = {
                    'task_id': f"ui-{int(time.time())}-{email}-{platform}",
                    'type': 'register_platform',
                    'timestamp': datetime.now().isoformat(),
                    'email': email,
                    'platform': platform.strip()
                }
                redis_client.rpush('task_queue', json.dumps(task_data))
                
            return jsonify({
                'success': True,
                'message': f"Queued registration tasks for {email} on {len(platforms)} platforms",
                'count': len(platforms)
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"Error: {str(e)}"
        }), 400

@app.route('/api/airdrop', methods=['POST'])
def api_airdrop():
    """API endpoint to participate in airdrops"""
    try:
        airdrop_name = request.form.get('airdrop_name')
        platform = request.form.get('platform', 'twitter')
        actions = request.form.get('actions', 'follow,retweet,like').split(',')
        
        if not airdrop_name:
            return jsonify({
                'success': False,
                'message': "Airdrop name is required"
            }), 400
        
        # Get accounts registered on the platform
        try:
            with open('/app/data/accounts.json', 'r') as f:
                accounts_data = json.load(f)
                
            eligible_accounts = []
            for account in accounts_data:
                platforms = account.get('platforms', {})
                if platform in platforms and platforms[platform].get('registered', False):
                    eligible_accounts.append(account)
            
            if not eligible_accounts:
                return jsonify({
                    'success': False,
                    'message': f"No accounts registered on {platform}"
                }), 400
            
            for account in eligible_accounts:
                task_data = {
                    'task_id': f"ui-{int(time.time())}-{account['email']}-{airdrop_name}",
                    'type': 'airdrop_participation',
                    'timestamp': datetime.now().isoformat(),
                    'email': account['email'],
                    'airdrop_name': airdrop_name,
                    'platform': platform,
                    'actions': [a.strip() for a in actions]
                }
                redis_client.rpush('task_queue', json.dumps(task_data))
            
            return jsonify({
                'success': True,
                'message': f"Queued {airdrop_name} airdrop participation for {len(eligible_accounts)} accounts",
                'count': len(eligible_accounts)
            })
        
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f"Error processing airdrop: {str(e)}"
            }), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"Error: {str(e)}"
        }), 400

@app.route('/api/import_proxies', methods=['POST'])
def api_import_proxies():
    """API endpoint to import proxies"""
    try:
        proxy_list = request.form.get('proxy_list', '')
        
        if not proxy_list.strip():
            return jsonify({
                'success': False,
                'message': "Proxy list is empty"
            }), 400
        
        # Store in Redis for the proxy checker to import
        redis_client.set('import_proxies', proxy_list)
        
        lines = [line for line in proxy_list.strip().split('\n') if line.strip()]
        
        return jsonify({
            'success': True,
            'message': f"Queued {len(lines)} proxies for import",
            'count': len(lines)
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"Error: {str(e)}"
        }), 400

@app.route('/api/clear_results', methods=['POST'])
def api_clear_results():
    """API endpoint to clear result queue"""
    try:
        redis_client.delete('result_queue')
        
        return jsonify({
            'success': True,
            'message': "Result queue cleared"
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"Error: {str(e)}"
        }), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)