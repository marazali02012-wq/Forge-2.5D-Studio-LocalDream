# Forge TripoSR on Oracle Ampere A1

Use an isolated Always Free eligible VM.Standard.A1.Flex VM. The current allowance is equivalent to 2 OCPUs and 12 GB RAM. Verify the free shape, region and disk allowance in the account before provisioning. Docker requires Ubuntu or another supported ARM64 host. The Dockerfile selects aarch64 Python wheels on that host.

Build from this directory. Generate a private runtime key on the VM and keep the env file mode 600. Use the exact Render editor origin in the CORS allowlist.

```sh
docker build -t forge-triposr:r70.34 .
umask 077
printf 'FORGE_API_TOKEN=%s\nFORGE_ALLOWED_ORIGINS=%s\n' "$(openssl rand -hex 32)" https://forge-r70-editor-preview.onrender.com > forge.env
docker run -d --restart unless-stopped --name forge-triposr \
  --env-file forge.env -p 127.0.0.1:7860:7860 forge-triposr:r70.34
curl -fsS http://127.0.0.1:7860/health
```

Place an HTTPS reverse proxy on the VM with the Forge hostname and an upload limit above 5 MiB. Proxy the hostname to `127.0.0.1:7860` and allow a 430-second response for CPU inference and rigging. Submit one fresh image from the Render editor to the HTTPS endpoint. Check that it returns a valid textured and animated GLB before offering it for use. The OCI deployment has yet to be run.
