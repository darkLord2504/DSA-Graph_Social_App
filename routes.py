from flask import render_template, request, redirect, url_for, flash, session
from app import app
import os
import networkx as nx
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# -------------------------------
# In‑Memory Data Structures
# -------------------------------
class SocialNetwork:
    def __init__(self):
        # following relationships: username -> set of usernames they follow
        self.graph = {}
        # messages: list of dicts { 'sender': ..., 'recipient': ..., 'content': ... }
        self.messages = []
        # pending block requests: list of dicts { 'requester': ..., 'target': ... }
        self.pending_blocks = []
        # temporary block relationships: dict mapping a blocking user to a set of blocked users
        self.temp_blocks = {}

    def add_user(self, username):
        if username not in self.graph:
            self.graph[username] = set()

    def delete_user(self, username):
        if username in self.graph:
            del self.graph[username]
        for user, follows in self.graph.items():
            follows.discard(username)
        self.messages = [msg for msg in self.messages if msg['sender'] != username and msg['recipient'] != username]
        self.pending_blocks = [req for req in self.pending_blocks if req['requester'] != username and req['target'] != username]
        if username in self.temp_blocks:
            del self.temp_blocks[username]
        for blocker in list(self.temp_blocks.keys()):
            self.temp_blocks[blocker].discard(username)

    def add_follow(self, follower, following):
        if follower in self.graph and following in self.graph:
            self.graph[follower].add(following)
            return True
        return False

    def remove_follow(self, follower, following):
        if follower in self.graph and following in self.graph[follower]:
            self.graph[follower].remove(following)
            return True
        return False

    def send_message(self, sender, recipient, content):
        # If the recipient has temporarily blocked the sender, do not allow sending.
        if recipient in self.temp_blocks and sender in self.temp_blocks[recipient]:
            return False
        if sender in self.graph and recipient in self.graph:
            self.messages.append({'sender': sender, 'recipient': recipient, 'content': content})
            return True
        return False

    def get_conversation(self, user1, user2):
        return [msg for msg in self.messages if (msg['sender'] == user1 and msg['recipient'] == user2) or (msg['sender'] == user2 and msg['recipient'] == user1)]

    def request_block(self, requester, target):
        if requester in self.graph and target in self.graph:
            for req in self.pending_blocks:
                if req['requester'] == requester and req['target'] == target:
                    return False
            self.pending_blocks.append({'requester': requester, 'target': target})
            return True
        return False

    def finalize_block(self, requester, target):
        if requester in self.graph and target in self.graph:
            if requester not in self.temp_blocks:
                self.temp_blocks[requester] = set()
            self.temp_blocks[requester].add(target)
            self.pending_blocks = [req for req in self.pending_blocks if not (req['requester'] == requester and req['target'] == target)]
            return True
        return False

    def unblock(self, requester, target):
        if requester in self.temp_blocks and target in self.temp_blocks[requester]:
            self.temp_blocks[requester].remove(target)
            return True
        return False

    def get_all_users(self):
        return list(self.graph.keys())

    def visualize(self):
        # Ensure the 'static' folder exists.
        if not os.path.exists('static'):
            os.makedirs('static')
        
        # Prepare sets for mutual and one-way (directed) follow edges.
        mutual_edges = set()
        directed_edges = set()
        
        for u in self.graph:
            for v in self.graph[u]:
                # Check if the follow is mutual.
                if u in self.graph.get(v, set()):
                    # Use a sorted tuple to avoid duplicate entries.
                    mutual_edges.add(tuple(sorted((u, v))))
                else:
                    directed_edges.add((u, v))
        
        # Get all nodes.
        nodes = list(self.graph.keys())
        
        # Create an undirected graph for mutual edges.
        G_mutual = nx.Graph()
        G_mutual.add_nodes_from(nodes)
        G_mutual.add_edges_from(mutual_edges)
        
        # Create a directed graph for one-way follows.
        G_directed = nx.DiGraph()
        G_directed.add_nodes_from(nodes)
        G_directed.add_edges_from(directed_edges)
        
        # Use the positions from the undirected graph (or compute for all nodes).
        pos = nx.spring_layout(G_mutual, k=1, iterations=50)
        
        plt.figure(figsize=(8, 8))
        # Draw nodes with white fill and dark blue borders.
        nx.draw_networkx_nodes(G_mutual, pos, node_color='white', edgecolors='darkblue', node_size=1700)
        nx.draw_networkx_labels(G_mutual, pos, font_color='black')
        
        # Draw mutual edges (undirected) in turquoise.
        if mutual_edges:
            nx.draw_networkx_edges(
                G_mutual,
                pos,
                edgelist=list(mutual_edges),
                edge_color='green',
                arrows=False,
                connectionstyle='arc3, rad=0.2'
            )
        
        # Draw one-way directed edges in turquoise with arrowheads.
        if directed_edges:
            nx.draw_networkx_edges(
                G_directed,
                pos,
                edgelist=list(directed_edges),
                edge_color='turquoise',
                arrows=True,
                arrowstyle='-|>',
                arrowsize=50  # Increase arrow size if necessary
            )
        
        # Draw block edges in red (always directed) from temporary block relationships.
        block_edges = []
        for blocker, blocked_set in self.temp_blocks.items():
            for blocked in blocked_set:
                block_edges.append((blocker, blocked))
        if block_edges:
            nx.draw_networkx_edges(
                G_directed,
                pos,
                edgelist=block_edges,
                edge_color='red',
                arrows=True,
                arrowstyle='-|>',
                arrowsize=20,
                width=2
            )
        
        plt.title("Bubble - Social Network Graph", color='darkblue')
        plt.savefig('static/graph.png')
        plt.close()

# Create a global instance
network = SocialNetwork()

# (Optional) Initialize some users and relationships for testing.
for user in ['Alice', 'Bob', 'Charlie', 'David', 'Eve']:
    network.add_user(user)
network.add_follow('Alice', 'Bob')
network.add_follow('Alice', 'Charlie')
network.add_follow('Bob', 'David')
network.add_follow('Charlie', 'David')
network.add_follow('David', 'Eve')
network.add_follow('Eve', 'Alice')

# -------------------------------
# Routes for User Side
# -------------------------------

@app.route('/intro')
def intro():
    return render_template('intro.html')

@app.route('/users')
def user_index():
    users = network.get_all_users()
    return render_template('index.html', users=users)

@app.route('/account/<username>')
def account(username):
    if username not in network.get_all_users():
        flash("User does not exist!")
        return redirect(url_for('user_index'))
    following = list(network.graph.get(username, []))
    followers = [user for user, follows in network.graph.items() if username in follows]
    all_users = network.get_all_users()
    return render_template('account.html', username=username, following=following, followers=followers, users=all_users)

@app.route('/chats/<username>')
def chats(username):
    if username not in network.get_all_users():
        flash("User does not exist!")
        return redirect(url_for('user_index'))
    conversation_partners = set()
    for msg in network.messages:
        if msg['sender'] == username:
            conversation_partners.add(msg['recipient'])
        elif msg['recipient'] == username:
            conversation_partners.add(msg['sender'])
    all_users = set(network.get_all_users()) - {username}
    new_partners = all_users - conversation_partners
    return render_template('chats.html', username=username, conversation_partners=conversation_partners, new_partners=new_partners)

@app.route('/conversation/<user>/<other>')
def conversation(user, other):
    if user not in network.get_all_users() or other not in network.get_all_users():
        flash("One of the users does not exist!")
        return redirect(url_for('user_index'))
    conv = network.get_conversation(user, other)
    return render_template('conversation.html', user=user, other=other, conversation=conv)

@app.route('/send_message/<sender>/<recipient>', methods=['POST'])
def send_message(sender, recipient):
    content = request.form.get('content')
    if content:
        # Check if the recipient has blocked the sender
        if recipient in network.temp_blocks and sender in network.temp_blocks[recipient]:
            flash("You have been temporarily blocked by that user.")
        else:
            success = network.send_message(sender, recipient, content)
            if success:
                flash("Message sent!")
            else:
                flash("Unable to send message.")
    return redirect(url_for('conversation', user=sender, other=recipient))

@app.route('/follow/<username>', methods=['POST'])
def follow(username):
    target = request.form.get('target')
    if target:
        success = network.add_follow(username, target)
        if success:
            flash(f"You are now following {target}.")
        else:
            flash("Unable to follow.")
    return redirect(url_for('account', username=username))

@app.route('/unfollow/<username>', methods=['POST'])
def unfollow(username):
    target = request.form.get('target')
    if target:
        success = network.remove_follow(username, target)
        if success:
            flash(f"You have unfollowed {target}.")
        else:
            flash("Unable to unfollow.")
    return redirect(url_for('account', username=username))

@app.route('/request_block/<username>', methods=['POST'])
def request_block(username):
    target = request.form.get('target')
    if target:
        network.request_block(username, target)
        flash(f"Block request for {target} sent to admin.")
    return redirect(url_for('account', username=username))

@app.route('/delete_account/<username>', methods=['POST'])
def delete_account(username):
    network.delete_user(username)
    flash("Your account has been deleted.")
    return redirect(url_for('user_index'))

# -------------------------------
# Routes for Admin Side
# -------------------------------

ADMIN_USERNAME = 'nkolarbi'
ADMIN_PASSWORD = 'adminpass'

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid credentials.")
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash("Logged out.")
    return redirect(url_for('intro'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    network.visualize()
    pending = network.pending_blocks
    temp_blocked = []
    for blocker, blocked_set in network.temp_blocks.items():
        for blocked in blocked_set:
            temp_blocked.append({'blocker': blocker, 'blocked': blocked})
    users = network.get_all_users()
    return render_template('admin.html', pending=pending, temp_blocked=temp_blocked, users=users)

@app.route('/admin/block', methods=['POST'])
def admin_block():
    requester = request.form.get('requester')
    target = request.form.get('target')
    if requester and target:
        success = network.finalize_block(requester, target)
        if success:
            flash(f"User {target} has been temporarily blocked by {requester}.")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/unblock', methods=['POST'])
def admin_unblock():
    requester = request.form.get('requester')
    target = request.form.get('target')
    if requester and target:
        success = network.unblock(requester, target)
        if success:
            flash(f"User {target} has been unblocked by {requester}.")
    return redirect(url_for('admin_dashboard'))

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        if username:
            if username in network.get_all_users():
                flash("User already exists!")
            else:
                network.add_user(username)
                flash(f"User {username} added!")
        return redirect(url_for('user_index'))
    return render_template('add_user.html')
