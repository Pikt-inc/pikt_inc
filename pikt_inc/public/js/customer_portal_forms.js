(function(){
  function closeOpenPortalMenus(){
    document.querySelectorAll('.portal-shell-menu[open]').forEach(function(menu){
      menu.removeAttribute('open');
    });
  }

  function bindPortalMenus(){
    document.addEventListener('click',function(event){
      document.querySelectorAll('.portal-shell-menu[open]').forEach(function(menu){
        if(menu.contains(event.target)){return;}
        menu.removeAttribute('open');
      });
    });

    document.addEventListener('keydown',function(event){
      if(event.key==='Escape'){
        closeOpenPortalMenus();
      }
    });

    document.querySelectorAll('.portal-shell-menu__panel a').forEach(function(link){
      link.addEventListener('click',function(){
        closeOpenPortalMenus();
      });
    });
  }

  function csrf(){
    var match=document.cookie.match(/(?:^|; )csrf_token=([^;]+)/);
    if(match){return decodeURIComponent(match[1]);}
    if(window.frappe&&frappe.csrf_token){return frappe.csrf_token;}
    if(window.csrf_token){return window.csrf_token;}
    return '';
  }

  function extractMessage(body){
    if(body&&body.message){body=body.message;}
    if(body&&body._server_messages){
      try{
        var messages=JSON.parse(body._server_messages);
        if(messages&&messages.length){return JSON.parse(messages[0]).message||'Unable to save changes.';}
      }catch(_error){}
    }
    if(body&&body.exc){return 'Unable to save changes.';}
    if(typeof body==='string'&&body){return body;}
    if(body&&body.message){return body.message;}
    return '';
  }

  async function submitForm(form){
    var endpoint=form.getAttribute('data-portal-endpoint');
    if(!endpoint){return;}
    closeOpenPortalMenus();
    var formData=new FormData(form);
    var payload={};
    formData.forEach(function(value,key){payload[key]=value;});

    var messageBox=form.querySelector('[data-portal-message]');
    if(messageBox){
      messageBox.classList.remove('is-visible','is-error');
      messageBox.textContent='';
    }

    try{
      var response=await fetch(endpoint,{
        method:'POST',
        credentials:'same-origin',
        headers:{
          'Content-Type':'application/json',
          'X-Frappe-CSRF-Token':csrf()
        },
        body:JSON.stringify(payload)
      });
      var body=await response.json().catch(function(){return {};});
      if(!response.ok||body.exc||body.exception){
        throw new Error(extractMessage(body)||'Unable to save changes.');
      }
      if(messageBox){
        messageBox.textContent=extractMessage(body)||'Changes saved.';
        messageBox.classList.add('is-visible');
      }
      window.setTimeout(function(){window.location.reload();},600);
    }catch(error){
      if(messageBox){
        messageBox.textContent=error.message||'Unable to save changes.';
        messageBox.classList.add('is-visible','is-error');
      }else{
        window.alert(error.message||'Unable to save changes.');
      }
    }
  }

  document.addEventListener('DOMContentLoaded',function(){
    bindPortalMenus();
    document.querySelectorAll('form[data-portal-endpoint]').forEach(function(form){
      form.addEventListener('submit',function(event){
        event.preventDefault();
        submitForm(form);
      });
    });
  });
})();
