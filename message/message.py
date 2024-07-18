class Message:
    def __init__(self, message_type, fid=0, swarm_id=0, dest_fid="*", dest_swarm_id="*",
                 radio_range=None, el=None, gtl=None, args=None):
        self.type = message_type
        self.fid = fid
        self.swarm_id = swarm_id
        self.dest_fid = dest_fid
        self.dest_swarm_id = dest_swarm_id
        self.range = radio_range
        self.el = el
        self.gtl = gtl
        self.args = args
        self.id = None

    def from_fls(self, ctx):
        self.fid = ctx.fid
        self.swarm_id = ctx.swarm_id
        self.el = ctx.el
        self.gtl = ctx.gtl
        if self.range is None:
            self.range = ctx.radio_range
        self.id = ctx.message_id
        return self

    def from_server(self, server_id=0):
        self.fid = server_id
        self.swarm_id = 0
        self.id = 0
        return self

    def to_all(self):
        self.dest_fid = "*"
        self.dest_swarm_id = "*"
        return self

    def to_swarm(self, ctx):
        self.dest_fid = "*"
        self.dest_swarm_id = ctx.swarm_id
        return self

    def to_fls(self, ctx):
        self.dest_fid = ctx.fid
        self.dest_swarm_id = ctx.swarm_id
        if hasattr(ctx, 'range'):
            self.range = ctx.range
        return self

    def to_fls_id(self, fid, swarm_id):
        self.dest_fid = fid
        self.dest_swarm_id = swarm_id
        return self

    def to_server(self, server_id=0):
        self.dest_fid = server_id
        self.dest_swarm_id = 0
        return self

    def __repr__(self):
        return f"{self.type.name} " \
               f"{self.fid} " \
               f"{self.dest_fid} "
