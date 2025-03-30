import os
import networkx as nx
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from flask import render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from app import app

# -------------------------------
# BFS-based Suggestions Function
# -------------------------------
def bfs_suggestions(graph, start, max_depth=2):
    """
    Performs BFS on the graph from 'start' up to max_depth.
    Returns a set of nodes reachable within max_depth (excluding direct friends and self).
    """
    from collections import deque
    visited = {start: 0}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        current_depth = visited[current]
        if current_depth < max_depth:
            for neighbor in graph.get(current, []):
                if neighbor not in visited:
                    visited[neighbor] = current_depth + 1
                    queue.append(neighbor)
    suggestions = set(visited.keys())
    suggestions.discard(start)
    # Exclude direct friends:
    suggestions -= graph[start]
    return suggestions

# -------------------------------
# In‑Memory Data Structures
# -------------------------------
class SocialNetwork:
    def __init__(self):
        self.graph = {}             # username -> set of usernames they follow
        self.messages = []          # list of dicts { 'sender', 'recipient', 'content' }
        self.pending_blocks = []    # list of block requests { 'requester', 'target' }
        self.temp_blocks = {}       # dict: blocker -> set(blocked)
        self.profile_pics = {}      # username -> filename (or None)

    def add_user(self, username):
        if username not in self.graph:
            self.graph[username] = set()
            self.profile_pics[username] = None

    def delete_user(self, username):
        if username in self.graph:
            del self.graph[username]
        for user, follows in self.graph.items():
            follows.discard(username)
        self.messages = [m for m in self.messages if m['sender'] != username and m['recipient'] != username]
        self.pending_blocks = [r for r in self.pending_blocks if r['requester'] != username and r['target'] != username]
        if username in self.temp_blocks:
            del self.temp_blocks[username]
        for blocker in list(self.temp_blocks.keys()):
            self.temp_blocks[blocker].discard(username)
        if username in self.profile_pics:
            del self.profile_pics[username]

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
        if recipient in self.temp_blocks and sender in self.temp_blocks[recipient]:
            return False
        if sender in self.graph and recipient in self.graph:
            self.messages.append({'sender': sender, 'recipient': recipient, 'content': content})
            return True
        return False

    def get_conversation(self, user1, user2):
        return [
            msg for msg in self.messages
            if (msg['sender'] == user1 and msg['recipient'] == user2) or (msg['sender'] == user2 and msg['recipient'] == user1)
        ]

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
            self.pending_blocks = [
                r for r in self.pending_blocks
                if not (r['requester'] == requester and r['target'] == target)
            ]
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
        if not os.path.exists('static'):
            os.makedirs('static')
        mutual_edges = set()
        directed_edges = set()
        for u in self.graph:
            for v in self.graph[u]:
                if u in self.graph.get(v, set()):
                    mutual_edges.add(tuple(sorted((u, v))))
                else:
                    directed_edges.add((u, v))
        nodes = list(self.graph.keys())
        G_mutual = nx.Graph()
        G_mutual.add_nodes_from(nodes)
        G_mutual.add_edges_from(mutual_edges)
        G_directed = nx.DiGraph()
        G_directed.add_nodes_from(nodes)
        G_directed.add_edges_from(directed_edges)
        pos = nx.spring_layout(G_mutual, k=0.8, iterations=50)
        plt.figure(figsize=(8,8))
        nx.draw_networkx_nodes(G_mutual, pos, node_color='white', edgecolors='darkblue', node_size=2000)
        nx.draw_networkx_labels(G_mutual, pos, font_color='black')
        if mutual_edges:
            nx.draw_networkx_edges(
                G_mutual,
                pos,
                edgelist=list(mutual_edges),
                edge_color='green',
                arrows=False,
                connectionstyle='arc3, rad=0.2'
            )
        if directed_edges:
            nx.draw_networkx_edges(
                G_directed,
                pos,
                edgelist=list(directed_edges),
                edge_color='turquoise',
                arrows=True,
                arrowstyle='-|>',
                arrowsize=50
            )
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

# Create global instance
network = SocialNetwork()

# INITIAL DATA: At startup, no one follows anyone and no messages exist.
# Users are created via the add_user route.

# -------------------------------
# Routes
# -------------------------------

@app.route('/intro')
def intro():
    return render_template('intro.html')

@app.route('/')
def root_redirect():
    return redirect(url_for('intro'))

@app.route('/users')
def user_index():
    users = network.get_all_users()
    # If no profile pic set, use default_avatar.png
    user_pics = {u: network.profile_pics[u] if network.profile_pics[u] else 'default_avatar.png' for u in users}
    return render_template('index.html', users=users, user_pics=user_pics)

@app.route('/account/<username>')
def account(username):
    if username not in network.get_all_users():
        flash("User does not exist!")
        return redirect(url_for('user_index'))
    following = list(network.graph[username])
    followers = [u for u, follows in network.graph.items() if username in follows]
    # Build dropdown lists for followers and following
    followers_list = [{'username': u, 'pic': network.profile_pics.get(u) if network.profile_pics.get(u) else 'default_avatar.png'} for u in followers]
    following_list = [{'username': u, 'pic': network.profile_pics.get(u) if network.profile_pics.get(u) else 'default_avatar.png'} for u in following]
    # Friend suggestions: users not followed by current user
    friend_suggestions = []
    for u in network.get_all_users():
        if u != username and u not in following:
            friend_suggestions.append({'username': u, 'follows_me': (username in network.graph[u])})
    # Chat partners: allow chatting with all users
    chat_partners = set(network.get_all_users())
    user_profile_pic = network.profile_pics.get(username) if network.profile_pics.get(username) else 'default_avatar.png'
    # People you might know (BFS-based suggestions)
    people_suggestions = bfs_suggestions(network.graph, username, max_depth=2)
    # Convert suggestions to the needed format, excluding direct friends and self
    people_you_might_know_list = []
    for suggested_user in people_suggestions:
        pic = network.profile_pics.get(suggested_user) if network.profile_pics.get(suggested_user) else 'default_avatar.png'
        follows_me = (username in network.graph[suggested_user])
        people_you_might_know_list.append({
            'username': suggested_user,
            'pic': pic,
            'follows_me': follows_me
        })
    # Load conversation if chatWith query parameter is provided
    chatWith = request.args.get('chatWith')
    current_conversation = []
    if chatWith and chatWith in network.get_all_users():
        current_conversation = network.get_conversation(username, chatWith)
    else:
        chatWith = None

    return render_template(
        'account.html',
        username=username,
        user_profile_pic=user_profile_pic,
        num_followers=len(followers),
        num_following=len(following),
        friend_suggestions=friend_suggestions,
        chat_partners=chat_partners,
        chatWith=chatWith,
        current_conversation=current_conversation,
        followers_list=followers_list,
        following_list=following_list,
        people_you_might_know_list=people_you_might_know_list
    )

@app.route('/upload_pic/<username>', methods=['POST'])
def upload_pic(username):
    if 'profile_pic' not in request.files:
        flash("No file selected.")
        return redirect(url_for('account', username=username))
    file = request.files['profile_pic']
    if file.filename == '':
        flash("No file selected.")
        return redirect(url_for('account', username=username))
    filename = secure_filename(file.filename)
    save_path = os.path.join('static', 'images', filename)
    file.save(save_path)
    network.profile_pics[username] = filename
    flash("Profile picture updated!")
    return redirect(url_for('account', username=username))

@app.route('/send_message/<sender>', methods=['POST'])
def send_message(sender):
    recipient = request.form.get('recipient')
    content = request.form.get('content')
    if content and recipient:
        if recipient in network.temp_blocks and sender in network.temp_blocks[recipient]:
            flash("You have been temporarily blocked by that user.")
        else:
            success = network.send_message(sender, recipient, content)
            if success:
                flash("Message sent!")
            else:
                flash("Unable to send message.")
    return redirect(url_for('account', username=sender, chatWith=recipient))

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

@app.route('/delete_account/<username>', methods=['POST'])
def delete_account(username):
    network.delete_user(username)
    flash("Your account has been deleted.")
    return redirect(url_for('user_index'))

@app.route('/request_block/<username>', methods=['POST'])
def request_block(username):
    target = request.form.get('target')
    if target:
        network.request_block(username, target)
        flash(f"Block request for {target} sent to admin.")
    return redirect(url_for('account', username=username))

@app.route('/admin')
def admin_dashboard():
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
